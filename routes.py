import json
from markupsafe import Markup
from flask import render_template, redirect, url_for, session, flash, request, jsonify
from functools import wraps
from app import db, bcrypt, socketio, login_manager
from app.forms import SeekerRegistrationForm, EmployerRegistrationForm, LoginForm, JobForm, JobApplicationForm, ReviewForm
from app.models import User, Employer, JobSeeker, Job, Application, Review, DirectHire, ChatRoom, ChatMessage, LocationService
import logging
from datetime import datetime, timedelta
from flask_socketio import emit, join_room
import math
from math import radians, sin, cos, sqrt, atan2
from flask_login import login_user, logout_user, current_user, login_required

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.info("Loading routes")

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Map configuration
MAP_PROVIDER = "openstreetmap"
MAPBOX_ACCESS_TOKEN = "your_mapbox_access_token_here"
GOOGLE_MAPS_API_KEY = "your_google_maps_api_key_here"

# Custom Jinja2 filter for escaping JavaScript
def escapejs(value):
    """Escape a string for use in JavaScript"""
    if value is None:
        return ''
    return Markup(json.dumps(str(value))[1:-1])

# Admin login required decorator
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin to access this page.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_app(app):
    # Register custom filters
    app.jinja_env.filters['escapejs'] = escapejs

    # Utility function to calculate distance between two coordinates
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in kilometers using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)
        
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

    # ===== ENHANCED MAP SEARCH API ROUTES =====

    @app.route('/api/search/map')
    def api_map_search():
        """API endpoint for dynamic map searches"""
        if 'user_id' not in session:
            return jsonify({'error': 'Please login first.'}), 401
        
        user = User.query.get(session['user_id'])
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        radius = request.args.get('radius', 25, type=int)
        skill = request.args.get('skill', '')
        
        if not lat or not lng:
            return jsonify({'error': 'Location coordinates required'}), 400
        
        try:
            if user.role == 'employer':
                # Search for job seekers
                seekers_query = JobSeeker.query.filter(
                    JobSeeker.latitude.isnot(None),
                    JobSeeker.longitude.isnot(None)
                )
                
                if skill:
                    seekers_query = seekers_query.filter(JobSeeker.skills.ilike(f'%{skill}%'))
                
                seekers = []
                for seeker in seekers_query.all():
                    distance = calculate_distance(lat, lng, seeker.latitude, seeker.longitude)
                    if distance <= radius:
                        seekers.append({
                            'id': seeker.id,
                            'name': seeker.jobseeker_name,
                            'skills': seeker.skills or 'No skills specified',
                            'location': seeker.location,
                            'experience': seeker.years_experience,
                            'lat': seeker.latitude,
                            'lng': seeker.longitude,
                            'distance': distance
                        })
                
                return jsonify({
                    'type': 'seekers',
                    'items': seekers,
                    'count': len(seekers),
                    'user_location': {'lat': lat, 'lng': lng},
                    'radius': radius
                })
                
            else:  # jobseeker
                # Search for jobs
                jobs_query = Job.query.filter(
                    Job.latitude.isnot(None),
                    Job.longitude.isnot(None)
                )
                
                if skill:
                    jobs_query = jobs_query.filter(Job.required_skills.ilike(f'%{skill}%'))
                
                jobs = []
                for job in jobs_query.all():
                    distance = calculate_distance(lat, lng, job.latitude, job.longitude)
                    if distance <= radius:
                        jobs.append({
                            'id': job.id,
                            'title': job.title,
                            'employer': job.employer.employer_name,
                            'location': job.location,
                            'pay': job.pay,
                            'skills': job.required_skills,
                            'lat': job.latitude,
                            'lng': job.longitude,
                            'distance': distance
                        })
                
                return jsonify({
                    'type': 'jobs',
                    'items': jobs,
                    'count': len(jobs),
                    'user_location': {'lat': lat, 'lng': lng},
                    'radius': radius
                })
                
        except Exception as e:
            logger.error(f"Map search error: {e}")
            return jsonify({'error': 'Search failed'}), 500

    @app.route('/api/geocode')
    def api_geocode():
        """API endpoint for geocoding locations"""
        location = request.args.get('location', '')
        if not location:
            return jsonify({'error': 'Location parameter required'}), 400
        
        try:
            coordinates = LocationService.get_coordinates(location)
            return jsonify(coordinates)
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return jsonify({'error': 'Geocoding failed'}), 500

    # ===== MAP ACTION ROUTES =====

    @app.route('/api/map/apply/<int:job_id>', methods=['POST'])
    def api_map_apply(job_id):
        """API endpoint for applying to jobs directly from map"""
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please login first.'}), 401
        
        user = User.query.get(session['user_id'])
        if user.role != 'jobseeker':
            return jsonify({'success': False, 'message': 'Only job seekers can apply for jobs.'}), 403
        
        job = Job.query.get_or_404(job_id)
        
        # Check if already applied
        existing_application = Application.query.filter_by(
            job_id=job_id, 
            jobseeker_id=user.jobseeker.id
        ).first()
        
        if existing_application:
            return jsonify({
                'success': False, 
                'message': 'You have already applied for this job.'
            }), 400
        
        try:
            # Create new application
            new_application = Application(
                job_id=job_id, 
                jobseeker_id=user.jobseeker.id
            )
            
            db.session.add(new_application)
            db.session.commit()
            
            logger.info(f"Job seeker {user.jobseeker.jobseeker_name} applied for job {job.title} via map")
            
            return jsonify({
                'success': True,
                'message': f'Successfully applied for {job.title}!',
                'application_id': new_application.id
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Map application error: {e}")
            return jsonify({
                'success': False, 
                'message': 'An error occurred while submitting your application.'
            }), 500

    @app.route('/api/map/hire/<int:jobseeker_id>', methods=['POST'])
    def api_map_hire(jobseeker_id):
        """API endpoint for hiring job seekers directly from map"""
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please login first.'}), 401
        
        user = User.query.get(session['user_id'])
        if user.role != 'employer':
            return jsonify({'success': False, 'message': 'Only employers can hire job seekers.'}), 403
        
        jobseeker = JobSeeker.query.get_or_404(jobseeker_id)
        
        # Check if already hired
        existing_hire = DirectHire.query.filter_by(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        ).first()
        
        if existing_hire:
            return jsonify({
                'success': False, 
                'message': f'You have already hired {jobseeker.jobseeker_name}.'
            }), 400
        
        try:
            # Create direct hire record
            new_hire = DirectHire(
                employer_id=user.employer.id,
                jobseeker_id=jobseeker_id
            )
            
            db.session.add(new_hire)
            db.session.commit()
            
            logger.info(f"Employer {user.employer.employer_name} hired {jobseeker.jobseeker_name} via map")
            
            return jsonify({
                'success': True,
                'message': f'Successfully hired {jobseeker.jobseeker_name}!',
                'hire_id': new_hire.id
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Map hire error: {e}")
            return jsonify({
                'success': False, 
                'message': 'An error occurred while hiring.'
            }), 500

    @app.route('/api/map/start_chat/<int:jobseeker_id>', methods=['POST'])
    def api_map_start_chat(jobseeker_id):
        """API endpoint for starting chat directly from map"""
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please login first.'}), 401
        
        user = User.query.get(session['user_id'])
        if user.role != 'employer':
            return jsonify({'success': False, 'message': 'Only employers can start chats.'}), 403
        
        jobseeker = JobSeeker.query.get_or_404(jobseeker_id)
        
        # Check if chat room already exists
        existing_room = ChatRoom.query.filter_by(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        ).first()
        
        if existing_room:
            return jsonify({
                'success': True,
                'message': 'Chat room already exists.',
                'room_id': existing_room.id,
                'redirect_url': url_for('chat_room', room_id=existing_room.id)
            })
        
        try:
            # Create new chat room
            new_room = ChatRoom(
                employer_id=user.employer.id,
                jobseeker_id=jobseeker_id
            )
            
            db.session.add(new_room)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Chat started with {jobseeker.jobseeker_name}!',
                'room_id': new_room.id,
                'redirect_url': url_for('chat_room', room_id=new_room.id)
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Map chat creation error: {e}")
            return jsonify({
                'success': False, 
                'message': 'An error occurred while starting chat.'
            }), 500

    @app.route('/api/map/job_details/<int:job_id>')
    def api_map_job_details(job_id):
        """API endpoint to get job details for map popups"""
        job = Job.query.get_or_404(job_id)
        
        return jsonify({
            'id': job.id,
            'title': job.title,
            'employer': job.employer.employer_name,
            'company': job.employer.company_name,
            'location': job.location,
            'pay': job.pay,
            'skills': job.required_skills,
            'description': job.description,
            'posted_at': job.posted_at.isoformat() if job.posted_at else None
        })

    @app.route('/api/map/seeker_details/<int:jobseeker_id>')
    def api_map_seeker_details(jobseeker_id):
        """API endpoint to get job seeker details for map popups"""
        seeker = JobSeeker.query.get_or_404(jobseeker_id)
        
        return jsonify({
            'id': seeker.id,
            'name': seeker.jobseeker_name,
            'skills': seeker.skills,
            'location': seeker.location,
            'experience': seeker.years_experience,
            'email': seeker.email,
            'gender': seeker.gender
        })

    @app.route('/')
    def index():
        logger.debug("Accessing index route")
        return render_template('index.html')

    # Admin Routes
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if session.get('admin_logged_in'):
            return redirect(url_for('admin_dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session['admin_logged_in'] = True
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials!', 'error')
        
        return render_template('admin_login.html')

    @app.route('/admin/dashboard')
    @admin_login_required
    def admin_dashboard():
        job_seekers = JobSeeker.query.all()
        employers = Employer.query.all()
        total_jobs = Job.query.count()
        
        return render_template('admin_dashboard.html', 
                             job_seekers=job_seekers, 
                             employers=employers,
                             total_jobs=total_jobs)

    @app.route('/admin/delete/jobseeker/<int:seeker_id>', methods=['POST'])
    @admin_login_required
    def delete_job_seeker(seeker_id):
        try:
            job_seeker = JobSeeker.query.get_or_404(seeker_id)
            user_id = job_seeker.user_id
            seeker_name = job_seeker.jobseeker_name
            
            logger.info(f"Starting deletion process for job seeker: {seeker_name} (ID: {seeker_id})")
            
            # Use transaction and no_autoflush for safety
            with db.session.no_autoflush:
                try:
                    # 1. Handle Chat Messages and Rooms
                    chat_rooms = ChatRoom.query.filter_by(jobseeker_id=seeker_id).all()
                    logger.info(f"Found {len(chat_rooms)} chat rooms to delete")
                    
                    for room in chat_rooms:
                        # Delete messages in this room
                        messages_count = ChatMessage.query.filter_by(room_id=room.id).count()
                        ChatMessage.query.filter_by(room_id=room.id).delete()
                        logger.info(f"Deleted {messages_count} messages from room {room.id}")
                    
                    # Delete the chat rooms
                    chat_rooms_deleted = ChatRoom.query.filter_by(jobseeker_id=seeker_id).delete()
                    logger.info(f"Deleted {chat_rooms_deleted} chat rooms")
                    
                    # 2. Delete Applications
                    apps_deleted = Application.query.filter_by(jobseeker_id=seeker_id).delete()
                    logger.info(f"Deleted {apps_deleted} applications")
                    
                    # 3. Delete Direct Hires
                    hires_deleted = DirectHire.query.filter_by(jobseeker_id=seeker_id).delete()
                    logger.info(f"Deleted {hires_deleted} direct hires")
                    
                    # 4. Delete Reviews (both given and received)
                    reviews_given = Review.query.filter_by(reviewer_id=user_id).delete()
                    reviews_received = Review.query.filter_by(reviewee_id=user_id).delete()
                    logger.info(f"Deleted {reviews_given} reviews given and {reviews_received} reviews received")
                    
                    # 5. Delete Job Seeker
                    db.session.delete(job_seeker)
                    logger.info(f"Deleted job seeker record: {seeker_name}")
                    
                    # 6. Delete User
                    user = User.query.get(user_id)
                    if user:
                        db.session.delete(user)
                        logger.info(f"Deleted user account for: {seeker_name}")
                    
                except Exception as inner_e:
                    logger.error(f"Error during deletion process: {inner_e}")
                    raise inner_e
            
            # Final commit
            db.session.commit()
            logger.info(f"Successfully completed deletion of job seeker: {seeker_name}")
            
            return jsonify({
                'success': True,
                'message': f'Job seeker {seeker_name} deleted successfully!'
            })
            
        except Exception as e:
            db.session.rollback()
            error_msg = f'Error deleting job seeker: {str(e)}'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'message': error_msg
            }), 500

    @app.route('/admin/delete/employer/<int:employer_id>', methods=['POST'])
    @admin_login_required
    def delete_employer(employer_id):
        try:
            employer = Employer.query.get_or_404(employer_id)
            user_id = employer.user_id
            employer_name = employer.employer_name
            
            logger.info(f"Starting deletion process for employer: {employer_name} (ID: {employer_id})")
            
            with db.session.no_autoflush:
                try:
                    # Get all jobs by this employer
                    jobs = Job.query.filter_by(employer_id=employer_id).all()
                    logger.info(f"Found {len(jobs)} jobs to delete")
                    
                    # Delete applications, reviews, and jobs
                    for job in jobs:
                        # Delete applications for this job
                        apps_count = Application.query.filter_by(job_id=job.id).count()
                        Application.query.filter_by(job_id=job.id).delete()
                        logger.info(f"Deleted {apps_count} applications for job {job.title}")
                        
                        # Delete reviews for this job
                        reviews_count = Review.query.filter_by(job_id=job.id).count()
                        Review.query.filter_by(job_id=job.id).delete()
                        logger.info(f"Deleted {reviews_count} reviews for job {job.title}")
                        
                        db.session.delete(job)
                        logger.info(f"Deleted job: {job.title}")
                    
                    # Delete chat messages and rooms
                    chat_rooms = ChatRoom.query.filter_by(employer_id=employer_id).all()
                    logger.info(f"Found {len(chat_rooms)} chat rooms to delete")
                    
                    for room in chat_rooms:
                        messages_count = ChatMessage.query.filter_by(room_id=room.id).count()
                        ChatMessage.query.filter_by(room_id=room.id).delete()
                        logger.info(f"Deleted {messages_count} messages from room {room.id}")
                    
                    ChatRoom.query.filter_by(employer_id=employer_id).delete()
                    logger.info(f"Deleted {len(chat_rooms)} chat rooms")
                    
                    # Delete direct hires
                    hires_deleted = DirectHire.query.filter_by(employer_id=employer_id).delete()
                    logger.info(f"Deleted {hires_deleted} direct hires")
                    
                    # Delete reviews by this employer user
                    reviews_given = Review.query.filter_by(reviewer_id=user_id).delete()
                    reviews_received = Review.query.filter_by(reviewee_id=user_id).delete()
                    logger.info(f"Deleted {reviews_given} reviews given and {reviews_received} reviews received")
                    
                    # Delete employer
                    db.session.delete(employer)
                    logger.info(f"Deleted employer record: {employer_name}")
                    
                    # Delete user account
                    user = User.query.get(user_id)
                    if user:
                        db.session.delete(user)
                        logger.info(f"Deleted user account for: {employer_name}")
                    
                except Exception as inner_e:
                    logger.error(f"Error during deletion process: {inner_e}")
                    raise inner_e
            
            db.session.commit()
            logger.info(f"Successfully completed deletion of employer: {employer_name}")
            
            return jsonify({
                'success': True,
                'message': f'Employer {employer_name} deleted successfully!'
            })
            
        except Exception as e:
            db.session.rollback()
            error_msg = f'Error deleting employer: {str(e)}'
            logger.error(error_msg)
            return jsonify({
                'success': False,
                'message': error_msg
            }), 500

    @app.route('/admin/logout')
    def admin_logout():
        session.pop('admin_logged_in', None)
        flash('Admin logged out successfully!', 'success')
        return redirect(url_for('index'))

    # User authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        logger.debug("Accessing login route")
        
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(phone=form.phone.data).first()
            if user and bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                session['user_id'] = user.id
                session['user_role'] = user.role
                
                if user.role == 'jobseeker':
                    session['user_name'] = user.jobseeker.jobseeker_name
                else:
                    session['user_name'] = user.employer.employer_name
                
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid phone number or password.', 'error')
        return render_template('login.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        logger.debug("Accessing register route")
        seeker_form = SeekerRegistrationForm()
        employer_form = EmployerRegistrationForm()
        return render_template('register.html', seeker_form=seeker_form, employer_form=employer_form)

    @app.route('/register/seeker', methods=['POST'])
    def register_seeker():
        logger.debug("Accessing register_seeker route")
        form = SeekerRegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(phone=form.phone.data).first():
                flash('Phone number already registered.', 'error')
                return render_template('register.html', seeker_form=form, employer_form=EmployerRegistrationForm())
            
            if User.query.filter_by(aadhaar_number=form.aadhaar.data).first():
                flash('Aadhaar number already registered.', 'error')
                return render_template('register.html', seeker_form=form, employer_form=EmployerRegistrationForm())
            
            skills = form.skills.data
            if skills == 'Other':
                other_skill = request.form.get('other_skill', '').strip()
                skills = other_skill or 'Other'
            
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            new_user = User(
                phone=form.phone.data, 
                password=hashed_password, 
                role='jobseeker',
                aadhaar_number=form.aadhaar.data
            )
            try:
                db.session.add(new_user)
                db.session.commit()
            except Exception as e:
                logger.error(f"Error registering user: {e}")
                db.session.rollback()
                flash('An error occurred during registration.', 'error')
                return render_template('register.html', seeker_form=form, employer_form=EmployerRegistrationForm())
            
            coordinates = LocationService.get_coordinates(form.location.data)
            
            new_jobseeker = JobSeeker(
                user_id=new_user.id,
                jobseeker_name=form.name.data,
                email=form.email.data,
                skills=skills,
                years_experience=form.years_experience.data,
                gender=form.gender.data,
                location=form.location.data,
                latitude=coordinates['latitude'],
                longitude=coordinates['longitude']
            )
            try:
                db.session.add(new_jobseeker)
                db.session.commit()
                
                session['user_id'] = new_user.id
                session['user_role'] = 'jobseeker'
                session['user_name'] = new_jobseeker.jobseeker_name
                
            except Exception as e:
                logger.error(f"Error creating jobseeker profile: {e}")
                db.session.rollback()
                flash('An error occurred during profile creation.', 'error')
                return render_template('register.html', seeker_form=form, employer_form=EmployerRegistrationForm())
            
            flash('Registration successful! Welcome to QuickHire!', 'success')
            return redirect(url_for('dashboard'))
        
        return render_template('register.html', seeker_form=form, employer_form=EmployerRegistrationForm())

    @app.route('/register/employer', methods=['POST'])
    def register_employer():
        logger.debug("Accessing register_employer route")
        form = EmployerRegistrationForm()
        if form.validate_on_submit():
            if User.query.filter_by(phone=form.phone.data).first():
                flash('Phone number already registered.', 'error')
                return render_template('register.html', seeker_form=SeekerRegistrationForm(), employer_form=form)
            
            if User.query.filter_by(aadhaar_number=form.aadhaar.data).first():
                flash('Aadhaar number already registered.', 'error')
                return render_template('register.html', seeker_form=SeekerRegistrationForm(), employer_form=form)
            
            hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
            new_user = User(
                phone=form.phone.data, 
                password=hashed_password, 
                role='employer',
                aadhaar_number=form.aadhaar.data
            )
            try:
                db.session.add(new_user)
                db.session.commit()
            except Exception as e:
                logger.error(f"Error registering user: {e}")
                db.session.rollback()
                flash('An error occurred during registration.', 'error')
                return render_template('register.html', seeker_form=SeekerRegistrationForm(), employer_form=form)
            
            coordinates = LocationService.get_coordinates(form.location.data)
            
            new_employer = Employer(
                user_id=new_user.id,
                employer_name=form.name.data,
                company_name=form.company_name.data,
                email=form.email.data,
                location=form.location.data,
                latitude=coordinates['latitude'],
                longitude=coordinates['longitude']
            )
            try:
                db.session.add(new_employer)
                db.session.commit()
                
                session['user_id'] = new_user.id
                session['user_role'] = 'employer'
                session['user_name'] = new_employer.employer_name
                
            except Exception as e:
                logger.error(f"Error creating employer profile: {e}")
                db.session.rollback()
                flash('An error occurred during profile creation.', 'error')
                return render_template('register.html', seeker_form=SeekerRegistrationForm(), employer_form=form)
            
            flash('Registration successful! Welcome to QuickHire!', 'success')
            return redirect(url_for('dashboard'))
        
        return render_template('register.html', seeker_form=SeekerRegistrationForm(), employer_form=form)

    @app.route('/dashboard')
    @login_required
    def dashboard():
        logger.debug("Accessing dashboard route")
        user = current_user
        
        if user.role == 'jobseeker':
            jobseeker = user.jobseeker
            
            direct_hires = DirectHire.query.filter_by(jobseeker_id=jobseeker.id).all()
            direct_hires_count = len(direct_hires)
            
            applied_employers = []
            for application in jobseeker.applications:
                if application.job.employer not in applied_employers:
                    applied_employers.append(application.job.employer)
            
            hired_employers = [hire.employer for hire in direct_hires]
            
            recent_employers = list(set(applied_employers + hired_employers))[:6]
            
            return render_template('seeker_dashboard.html', 
                                 current_user=jobseeker,
                                 direct_hires=direct_hires,
                                 direct_hires_count=direct_hires_count,
                                 recent_employers=recent_employers,
                                 employers_count=len(recent_employers))
        else:
            employer = user.employer
            jobs = Job.query.filter_by(employer_id=employer.id).all()
            total_applicants = sum(len(job.applications) for job in jobs)
            
            applied_seekers = []
            for job in jobs:
                for application in job.applications:
                    if application.jobseeker not in applied_seekers:
                        applied_seekers.append(application.jobseeker)
            
            hired_seekers = [hire.jobseeker for hire in DirectHire.query.filter_by(employer_id=employer.id).all()]
            
            recent_seekers = list(set(applied_seekers + hired_seekers))[:6]
            
            return render_template('employer_dashboard.html', 
                                 current_user=employer, 
                                 total_applicants=total_applicants,
                                 recent_seekers=recent_seekers,
                                 jobs=jobs)

    @app.route('/check_new_hires')
    @login_required
    def check_new_hires():
        """Check if job seeker has new direct hires (for notifications)"""
        user = current_user
        if user.role != 'jobseeker':
            return jsonify({'new_hires': 0})
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        new_hires_count = DirectHire.query.filter(
            DirectHire.jobseeker_id == user.jobseeker.id,
            DirectHire.hired_at >= seven_days_ago
        ).count()
        
        return jsonify({'new_hires': new_hires_count})

    @app.route('/applicants')
    @login_required
    def applicants():
        logger.debug("Accessing applicants route")
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        jobs = Job.query.filter_by(employer_id=user.employer.id).all()
        total_pending = sum(len([app for app in job.applications if app.status == 'pending']) for job in jobs)
        total_hired = sum(len([app for app in job.applications if app.status == 'hired']) for job in jobs)
        total_rejected = sum(len([app for app in job.applications if app.status == 'rejected']) for job in jobs)
        
        return render_template('applicants.html', 
                             jobs=jobs, 
                             total_pending=total_pending, 
                             total_hired=total_hired, 
                             total_rejected=total_rejected,
                             current_user=user)

    @app.route('/post_job', methods=['GET', 'POST'])
    @login_required
    def post_job():
        logger.debug("Accessing post_job route")
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        form = JobForm()
        if form.validate_on_submit():
            try:
                skills = form.required_skills.data
                if skills == 'Other':
                    other_skill = request.form.get('other_skill', '').strip()
                    skills = other_skill or 'Other'
                
                # Get coordinates for location
                coordinates = LocationService.get_coordinates(form.location.data)
                
                new_job = Job(
                    employer_id=user.employer.id,
                    title=form.title.data,
                    description=form.description.data,
                    pay=float(form.pay.data),
                    location=form.location.data,
                    required_skills=skills,
                    latitude=coordinates['latitude'],
                    longitude=coordinates['longitude']
                )
                
                db.session.add(new_job)
                db.session.commit()
                
                flash('Job posted successfully!', 'success')
                logger.info(f"Job '{form.title.data}' posted successfully by {user.employer.employer_name}")
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error posting job: {str(e)}")
                flash(f'An error occurred while posting the job: {str(e)}', 'error')
        
        if form.errors:
            logger.error(f"Form validation errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{getattr(form, field).label.text}: {error}', 'error')
        
        return render_template('post_job.html', form=form)

    @app.route('/jobs')
    def jobs():
        logger.debug("Accessing jobs route")
        jobs = Job.query.all()
        user = current_user if current_user.is_authenticated else None
        return render_template('jobs.html', jobs=jobs, user=user)

    @app.route('/apply_job/<int:job_id>', methods=['GET', 'POST'])
    @login_required
    def apply_job(job_id):
        logger.debug(f"Accessing apply_job route for job_id: {job_id}")
        user = current_user
        if user.role != 'jobseeker':
            flash('Only job seekers can apply for jobs.', 'error')
            return redirect(url_for('dashboard'))
        
        job = Job.query.get_or_404(job_id)
        form = JobApplicationForm(job_id=job_id)
        if form.validate_on_submit():
            existing_application = Application.query.filter_by(job_id=job_id, jobseeker_id=user.jobseeker.id).first()
            if existing_application:
                flash('You have already applied for this job.', 'error')
                return redirect(url_for('jobs'))
            
            new_application = Application(job_id=job_id, jobseeker_id=user.jobseeker.id)
            try:
                db.session.add(new_application)
                db.session.commit()
                flash('Application submitted successfully!', 'success')
                return redirect(url_for('jobs'))
            except Exception as e:
                logger.error(f"Error submitting application: {e}")
                db.session.rollback()
                flash('An error occurred while submitting your application.', 'error')
        
        return render_template('apply_job.html', form=form, job=job)

    # ===== PROFILE EDITING ROUTES =====
    
    @app.route('/edit_jobseeker_profile', methods=['GET', 'POST'])
    @login_required
    def edit_jobseeker_profile():
        """Edit job seeker profile"""
        user = current_user
        if user.role != 'jobseeker':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        jobseeker = user.jobseeker
        
        if request.method == 'POST':
            try:
                # Update job seeker details
                jobseeker.jobseeker_name = request.form.get('name', jobseeker.jobseeker_name)
                jobseeker.email = request.form.get('email', jobseeker.email)
                jobseeker.skills = request.form.get('skills', jobseeker.skills)
                jobseeker.years_experience = int(request.form.get('years_experience', jobseeker.years_experience or 0))
                jobseeker.gender = request.form.get('gender', jobseeker.gender)
                jobseeker.location = request.form.get('location', jobseeker.location)
                
                # Update coordinates if location changed
                if jobseeker.location != request.form.get('location', ''):
                    coordinates = LocationService.get_coordinates(jobseeker.location)
                    jobseeker.latitude = coordinates['latitude']
                    jobseeker.longitude = coordinates['longitude']
                
                db.session.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating profile: {e}")
                flash('An error occurred while updating your profile.', 'error')
        
        return redirect(url_for('profile', user_id=user.id, edit=True))

    @app.route('/update_jobseeker_profile', methods=['POST'])
    @login_required
    def update_jobseeker_profile():
        """Update job seeker profile via AJAX"""
        user = current_user
        if user.role != 'jobseeker':
            return jsonify({'success': False, 'message': 'Access denied.'})
        
        try:
            jobseeker = user.jobseeker
            
            # Update fields
            jobseeker.jobseeker_name = request.form.get('name', jobseeker.jobseeker_name)
            jobseeker.email = request.form.get('email', jobseeker.email)
            jobseeker.skills = request.form.get('skills', jobseeker.skills)
            
            years_exp = request.form.get('years_experience')
            if years_exp:
                jobseeker.years_experience = int(years_exp)
            
            jobseeker.gender = request.form.get('gender', jobseeker.gender)
            jobseeker.location = request.form.get('location', jobseeker.location)
            
            # Update coordinates if location changed
            if jobseeker.location != request.form.get('location', ''):
                coordinates = LocationService.get_coordinates(jobseeker.location)
                jobseeker.latitude = coordinates['latitude']
                jobseeker.longitude = coordinates['longitude']
            
            db.session.commit()
            
            # Update session name if changed
            if 'user_name' in session:
                session['user_name'] = jobseeker.jobseeker_name
            
            return jsonify({
                'success': True, 
                'message': 'Profile updated successfully!',
                'data': {
                    'name': jobseeker.jobseeker_name,
                    'email': jobseeker.email,
                    'skills': jobseeker.skills,
                    'years_experience': jobseeker.years_experience,
                    'gender': jobseeker.gender,
                    'location': jobseeker.location
                }
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile: {e}")
            return jsonify({'success': False, 'message': 'An error occurred while updating your profile.'})

    @app.route('/profile/<int:user_id>')
    def profile(user_id):
        logger.debug(f"Accessing profile route for user_id: {user_id}")
        user = User.query.get_or_404(user_id)
        
        # Check if user is viewing their own profile
        is_own_profile = current_user.is_authenticated and current_user.id == user_id
        
        # Determine profile type and data
        if user.role == 'employer':
            profile = user.employer
            profile_type = 'employer'
        else:
            profile = user.jobseeker
            profile_type = 'jobseeker'
        
        # Check if edit mode is requested and user has permission
        edit_mode = request.args.get('edit', False) and is_own_profile
        
        return render_template('profile.html', 
                             profile=profile, 
                             user=user, 
                             profile_type=profile_type,
                             current_user=current_user if current_user.is_authenticated else None,
                             edit_mode=edit_mode,
                             is_own_profile=is_own_profile)

    @app.route('/update_employer_profile', methods=['POST'])
    @login_required
    def update_employer_profile():
        """Update employer profile via AJAX"""
        user = current_user
        if user.role != 'employer':
            return jsonify({'success': False, 'message': 'Access denied.'})
        
        try:
            employer = user.employer
            
            # Update fields
            employer.employer_name = request.form.get('name', employer.employer_name)
            employer.company_name = request.form.get('company_name', employer.company_name)
            employer.email = request.form.get('email', employer.email)
            employer.location = request.form.get('location', employer.location)
            
            # Update coordinates if location changed
            if employer.location != request.form.get('location', ''):
                coordinates = LocationService.get_coordinates(employer.location)
                employer.latitude = coordinates['latitude']
                employer.longitude = coordinates['longitude']
            
            db.session.commit()
            
            # Update session name if changed
            if 'user_name' in session:
                session['user_name'] = employer.employer_name
            
            return jsonify({
                'success': True, 
                'message': 'Profile updated successfully!',
                'data': {
                    'name': employer.employer_name,
                    'company_name': employer.company_name,
                    'email': employer.email,
                    'location': employer.location
                }
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating employer profile: {e}")
            return jsonify({'success': False, 'message': 'An error occurred while updating your profile.'})

    @app.route('/logout')
    @login_required
    def logout():
        logger.debug("Accessing logout route")
        logout_user()
        session.pop('user_id', None)
        session.pop('user_role', None)
        session.pop('user_name', None)
        flash('You have been logged out.', 'success')
        return redirect(url_for('index'))

    @app.route('/reject_application/<int:application_id>', methods=['POST'])
    @login_required
    def reject_application(application_id):
        logger.debug(f"Accessing reject_application route for application_id: {application_id}")
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        application = Application.query.get_or_404(application_id)
        employer = Employer.query.filter_by(user_id=user.id).first()
        if application.job.employer_id != employer.id:
            flash('Access denied. You can only manage your own job applications.', 'error')
            return redirect(url_for('applicants'))
        
        application.status = 'rejected'
        try:
            db.session.commit()
            flash('Application rejected successfully.', 'success')
        except Exception as e:
            logger.error(f"Error rejecting application: {e}")
            db.session.rollback()
            flash('An error occurred while rejecting the application.', 'error')
        
        return redirect(url_for('applicants'))

    @app.route('/hire_application/<int:application_id>', methods=['POST'])
    @login_required
    def hire_application(application_id):
        logger.debug(f"Accessing hire_application route for application_id: {application_id}")
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        application = Application.query.get_or_404(application_id)
        employer = Employer.query.filter_by(user_id=user.id).first()
        if application.job.employer_id != employer.id:
            flash('Access denied. You can only manage your own job applications.', 'error')
            return redirect(url_for('applicants'))
        
        application.status = 'hired'
        try:
            db.session.commit()
            flash('Application hired successfully. Phone number is now visible.', 'success')
        except Exception as e:
            logger.error(f"Error hiring application: {e}")
            db.session.rollback()
            flash('An error occurred while hiring the application.', 'error')
        
        return redirect(url_for('applicants'))

    @app.route('/search')
    def search_jobs():
        logger.debug("Accessing search_jobs route")
        query = request.args.get('q', '')
        location = request.args.get('location', '')
        skill = request.args.get('skill', '')
        min_salary = request.args.get('min_salary', 0, type=float)
        
        jobs = Job.query
        if query:
            jobs = jobs.filter(Job.title.ilike(f'%{query}%') | Job.description.ilike(f'%{query}%'))
        if location:
            jobs = jobs.filter(Job.location.ilike(f'%{location}%'))
        if skill:
            jobs = jobs.filter(Job.required_skills.ilike(f'%{skill}%'))
        if min_salary:
            jobs = jobs.filter(Job.pay >= min_salary)
        
        jobs = jobs.all()
        user = current_user if current_user.is_authenticated else None
        return render_template('jobs.html', jobs=jobs, user=user, search_mode=True)

    @app.route('/review/<int:job_id>', methods=['GET', 'POST'])
    @login_required
    def review(job_id):
        logger.debug(f"Accessing review route for job_id: {job_id}")
        user = current_user
        job = Job.query.get_or_404(job_id)
        
        # Determine if the user is reviewing as a jobseeker or employer
        if user.role == 'jobseeker':
            # Jobseeker reviewing employer
            application = Application.query.filter_by(job_id=job_id, jobseeker_id=user.jobseeker.id).first()
            if not application or application.status != 'hired':
                flash('You can only review jobs you have been hired for.', 'error')
                return redirect(url_for('dashboard'))
            reviewee = job.employer.user
        else:  # user.role == 'employer'
            # Employer reviewing jobseeker
            if job.employer.user_id != user.id:
                flash('You can only review job seekers for jobs you posted.', 'error')
                return redirect(url_for('applicants'))
            application = Application.query.filter_by(job_id=job_id, status='hired').first()
            if not application:
                flash('No hired job seekers found for this job.', 'error')
                return redirect(url_for('applicants'))
            reviewee = application.jobseeker.user
        
        # Check for existing review
        existing_review = Review.query.filter_by(reviewer_id=user.id, job_id=job_id, reviewee_id=reviewee.id).first()
        if existing_review:
            flash('You have already reviewed this job.', 'error')
            return redirect(url_for('dashboard') if user.role == 'jobseeker' else url_for('applicants'))
        
        form = ReviewForm()
        if form.validate_on_submit():
            # Convert rating to int before saving
            rating_value = int(form.rating.data)
            new_review = Review(
                reviewer_id=user.id,
                reviewee_id=reviewee.id,
                job_id=job_id,
                rating=rating_value,
                comment=form.comment.data
            )
            try:
                db.session.add(new_review)
                db.session.commit()
                flash('Review submitted successfully!', 'success')
                return redirect(url_for('dashboard') if user.role == 'jobseeker' else url_for('applicants'))
            except Exception as e:
                logger.error(f"Error submitting review: {e}")
                db.session.rollback()
                flash('An error occurred while submitting your review.', 'error')
        
        return render_template('review.html', form=form, job=job, reviewee=reviewee)

    @app.route('/review_seeker/<int:application_id>', methods=['GET', 'POST'])
    @login_required
    def review_seeker(application_id):
        logger.debug(f"Accessing review_seeker route for application_id: {application_id}")
        user = current_user
        if user.role != 'employer':
            flash('Access denied. Only employers can review job seekers.', 'error')
            return redirect(url_for('dashboard'))
        
        # Get the application and verify ownership
        application = Application.query.get_or_404(application_id)
        if application.job.employer_id != user.employer.id:
            flash('Access denied. You can only review job seekers you hired.', 'error')
            return redirect(url_for('applicants'))
        
        if application.status != 'hired':
            flash('You can only review hired job seekers.', 'error')
            return redirect(url_for('applicants'))
        
        # Check if review already exists
        existing_review = Review.query.filter_by(
            reviewer_id=user.id,
            reviewee_id=application.jobseeker.user.id,
            job_id=application.job_id
        ).first()
        
        if existing_review:
            flash('You have already reviewed this job seeker for this job.', 'error')
            return redirect(url_for('applicants'))
        
        form = ReviewForm()
        
        # DEBUG: Log form submission
        if request.method == 'POST':
            logger.debug(f"Form submitted with data: {request.form}")
            logger.debug(f"Form validation: {form.validate_on_submit()}")
            if form.errors:
                logger.debug(f"Form errors: {form.errors}")
        
        if form.validate_on_submit():
            # FIXED: Convert rating from string to int before saving
            rating_value = int(form.rating.data)
            logger.debug(f"Creating review with rating: {rating_value}")
            new_review = Review(
                reviewer_id=user.id,
                reviewee_id=application.jobseeker.user.id,
                job_id=application.job_id,
                rating=rating_value,
                comment=form.comment.data
            )
            try:
                db.session.add(new_review)
                db.session.commit()
                flash('Review submitted successfully! The job seeker can now see your feedback on their profile.', 'success')
                return redirect(url_for('applicants'))
            except Exception as e:
                logger.error(f"Error submitting review: {e}")
                db.session.rollback()
                flash('An error occurred while submitting your review. Please try again.', 'error')
    
        return render_template('review_seeker.html', 
                             form=form, 
                             jobseeker=application.jobseeker,
                             job=application.job,
                             application=application,
                             current_user=user)

    # ADD MISSING ROUTE FOR SUBMIT REVIEW
    @app.route('/submit_review_seeker/<int:application_id>', methods=['POST'])
    def submit_review_seeker(application_id):
        """Route to handle review submission from review_seeker.html"""
        return review_seeker(application_id)

    # ===== NEW REVIEW EMPLOYER ROUTE =====
    
    @app.route('/review_employer/<int:employer_id>', methods=['GET', 'POST'])
    @login_required
    def review_employer(employer_id):
        """Job seeker reviewing an employer"""
        user = current_user
        if user.role != 'jobseeker':
            flash('Access denied. Only job seekers can review employers.', 'error')
            return redirect(url_for('dashboard'))
        
        employer = Employer.query.get_or_404(employer_id)
        
        # Check if job seeker was hired by this employer
        direct_hire = DirectHire.query.filter_by(
            employer_id=employer_id,
            jobseeker_id=user.jobseeker.id
        ).first()
        
        if not direct_hire:
            flash('You can only review employers who have hired you.', 'error')
            return redirect(url_for('my_hires'))
        
        # Check if review already exists
        existing_review = Review.query.filter_by(
            reviewer_id=user.id,
            reviewee_id=employer.user.id
        ).first()
        
        if existing_review:
            flash('You have already reviewed this employer.', 'error')
            return redirect(url_for('my_hires'))
        
        form = ReviewForm()
        
        if form.validate_on_submit():
            try:
                rating_value = int(form.rating.data)
                
                # Create a dummy job for the review
                dummy_job = Job.query.filter_by(employer_id=employer_id).first()
                if not dummy_job:
                    dummy_job = Job(
                        employer_id=employer_id,
                        title="Direct Hire Position",
                        description="Direct employment",
                        pay=0,
                        location=employer.location,
                        required_skills="Various"
                    )
                    db.session.add(dummy_job)
                    db.session.flush()
                
                new_review = Review(
                    reviewer_id=user.id,
                    reviewee_id=employer.user.id,
                    job_id=dummy_job.id,
                    rating=rating_value,
                    comment=form.comment.data
                )
                
                db.session.add(new_review)
                db.session.commit()
                
                flash('Review submitted successfully! Thank you for your feedback.', 'success')
                return redirect(url_for('my_hires'))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error submitting employer review: {e}")
                flash('An error occurred while submitting your review. Please try again.', 'error')
        
        return render_template('review_employer.html', 
                             form=form, 
                             employer=employer,
                             current_user=user)

    # ===== MAP ROUTES =====

    @app.route('/map/jobs')
    @login_required
    def map_jobs():
        """Interactive map for job seekers to find nearby jobs"""
        user = current_user
        if user.role != 'jobseeker':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        # Get filter parameters
        user_lat = request.args.get('lat', type=float)
        user_lng = request.args.get('lng', type=float)
        radius = request.args.get('radius', 25, type=int)
        skill_filter = request.args.get('skill', '')
        location = request.args.get('location', '')
        
        # Get jobs with coordinates
        jobs_query = Job.query.filter(Job.latitude.isnot(None), Job.longitude.isnot(None))
        
        # Apply skill filter
        if skill_filter:
            jobs_query = jobs_query.filter(Job.required_skills.ilike(f'%{skill_filter}%'))
        
        # If user location provided, filter by distance
        if user_lat and user_lng:
            jobs = []
            for job in jobs_query.all():
                if job.latitude and job.longitude:
                    distance = calculate_distance(user_lat, user_lng, job.latitude, job.longitude)
                    if distance <= radius:
                        job.distance = distance
                        jobs.append(job)
        else:
            jobs = jobs_query.all()
            for job in jobs:
                job.distance = None
        
        return render_template('map_jobs.html', 
                             jobs=jobs,
                             user_lat=user_lat,
                             user_lng=user_lng,
                             radius=radius,
                             skill_filter=skill_filter,
                             map_provider=MAP_PROVIDER,
                             mapbox_token=MAPBOX_ACCESS_TOKEN,
                             google_maps_key=GOOGLE_MAPS_API_KEY)

    @app.route('/map/seekers')
    @login_required
    def map_seekers():
        """Interactive map for employers to find nearby job seekers"""
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        # Get filter parameters
        user_lat = request.args.get('lat', type=float)
        user_lng = request.args.get('lng', type=float)
        radius = request.args.get('radius', 25, type=int)
        skill_filter = request.args.get('skill', '')
        location = request.args.get('location', '')
        
        # Get job seekers with coordinates
        seekers_query = JobSeeker.query.filter(
            JobSeeker.latitude.isnot(None), 
            JobSeeker.longitude.isnot(None)
        )
        
        # Apply skill filter
        if skill_filter:
            seekers_query = seekers_query.filter(JobSeeker.skills.ilike(f'%{skill_filter}%'))
        
        # If user location provided, filter by distance
        seekers = []
        if user_lat and user_lng:
            for seeker in seekers_query.all():
                if seeker.latitude and seeker.longitude:
                    distance = calculate_distance(user_lat, user_lng, seeker.latitude, seeker.longitude)
                    if distance <= radius:
                        seeker.distance = distance
                        seekers.append(seeker)
        else:
            seekers = seekers_query.all()
            for seeker in seekers:
                seeker.distance = None
        
        # Get hired seeker IDs for this employer
        hired_seeker_ids = [hire.jobseeker_id for hire in DirectHire.query.filter_by(employer_id=user.employer.id).all()]
        
        # Debug logging
        logger.info(f"Employer map: {len(seekers)} seekers found, user_lat: {user_lat}, user_lng: {user_lng}")
        
        return render_template('map_seeker.html',
                             seekers=seekers,
                             user_lat=user_lat,
                             user_lng=user_lng,
                             radius=radius,
                             skill_filter=skill_filter,
                             hired_seeker_ids=hired_seeker_ids,
                             map_provider=MAP_PROVIDER,
                             mapbox_token=MAPBOX_ACCESS_TOKEN,
                             google_maps_key=GOOGLE_MAPS_API_KEY)

    @app.route('/api/geolocate')
    def api_geolocate():
        """API endpoint to get coordinates for a location"""
        location = request.args.get('location', '')
        if not location:
            return jsonify({'error': 'Location parameter required'}), 400
        
        coordinates = LocationService.get_coordinates(location)
        return jsonify(coordinates)
    
    # ===== ADD THE NEW ROUTE INSIDE THE INIT_APP FUNCTION =====
    
    @app.route('/submit_direct_review/<int:jobseeker_id>', methods=['POST'])
    @login_required
    def submit_direct_review(jobseeker_id):
        """Submit review for directly hired job seeker"""
        user = current_user
        if user.role != 'employer':
            return jsonify({'success': False, 'message': 'Only employers can review job seekers.'})
        
        jobseeker = JobSeeker.query.get_or_404(jobseeker_id)
        
        # Check if job seeker was hired by this employer
        direct_hire = DirectHire.query.filter_by(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        ).first()
        
        if not direct_hire:
            return jsonify({'success': False, 'message': 'You can only review job seekers you have hired.'})
        
        # Check if review already exists
        existing_review = Review.query.filter_by(
            reviewer_id=user.id,
            reviewee_id=jobseeker.user.id
        ).first()
        
        if existing_review:
            return jsonify({'success': False, 'message': 'You have already reviewed this job seeker.'})
        
        try:
            rating = int(request.form.get('rating'))
            comment = request.form.get('comment', '')
            
            # Create a dummy job for the review (since direct hires don't have job associations)
            dummy_job = Job.query.filter_by(employer_id=user.employer.id).first()
            if not dummy_job:
                # Create a minimal job record if none exists
                dummy_job = Job(
                    employer_id=user.employer.id,
                    title="Direct Hire",
                    description="Direct hiring",
                    pay=0,
                    location=user.employer.location,
                    required_skills="Various"
                )
                db.session.add(dummy_job)
                db.session.flush()  # Get the ID without committing
            
            new_review = Review(
                reviewer_id=user.id,
                reviewee_id=jobseeker.user.id,
                job_id=dummy_job.id,
                rating=rating,
                comment=comment
            )
            
            db.session.add(new_review)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Review submitted successfully!'
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error submitting direct review: {e}")
            return jsonify({'success': False, 'message': 'An error occurred while submitting your review.'})

    # ===== NEW FEATURES: DIRECT HIRE AND CHAT =====

    @app.route('/direct_hire')
    @login_required
    def direct_hire():
        """Direct hiring interface for employers"""
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        # Get filter parameters
        category = request.args.get('category', 'all')
        search_query = request.args.get('search', '')
        
        # Base query for job seekers
        job_seekers_query = JobSeeker.query
        
        # Apply category filter
        if category != 'all':
            job_seekers_query = job_seekers_query.filter(JobSeeker.skills.ilike(f'%{category}%'))
        
        # Apply search filter
        if search_query:
            job_seekers_query = job_seekers_query.filter(
                db.or_(
                    JobSeeker.jobseeker_name.ilike(f'%{search_query}%'),
                    JobSeeker.skills.ilike(f'%{search_query}%'),
                    JobSeeker.location.ilike(f'%{search_query}%')
                )
            )
        
        job_seekers = job_seekers_query.all()
        
        # Get already hired job seekers for this employer
        hired_seeker_ids = [hire.jobseeker_id for hire in DirectHire.query.filter_by(employer_id=user.employer.id).all()]
        
        return render_template('direct_hire.html',
                             job_seekers=job_seekers,
                             hired_seeker_ids=hired_seeker_ids,
                             current_category=category,
                             search_query=search_query,
                             current_user=user)

    @app.route('/hire_directly/<int:jobseeker_id>', methods=['POST'])
    @login_required
    def hire_directly(jobseeker_id):
        """Directly hire a job seeker"""
        user = current_user
        if user.role != 'employer':
            return jsonify({'success': False, 'message': 'Access denied.'})
        
        jobseeker = JobSeeker.query.get_or_404(jobseeker_id)
        
        # Check if already hired
        existing_hire = DirectHire.query.filter_by(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        ).first()
        
        if existing_hire:
            return jsonify({'success': False, 'message': 'You have already hired this job seeker.'})
        
        # Create direct hire record
        new_hire = DirectHire(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        )
        
        try:
            db.session.add(new_hire)
            db.session.commit()
            
            # Here you can add notification logic (email, SMS, etc.)
            logger.info(f"Employer {user.employer.employer_name} directly hired {jobseeker.jobseeker_name}")
            
            return jsonify({
                'success': True,
                'message': f'Successfully hired {jobseeker.jobseeker_name}!'
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in direct hire: {e}")
            return jsonify({'success': False, 'message': 'An error occurred while hiring.'})

    @app.route('/hired_seekers')
    @login_required
    def hired_seekers():
        """View directly hired job seekers"""
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        direct_hires = DirectHire.query.filter_by(employer_id=user.employer.id).all()
        
        return render_template('hired_seekers.html',
                             direct_hires=direct_hires,
                             current_user=user)

    @app.route('/my_hires')
    @login_required
    def my_hires():
        """View direct hires from job seeker perspective"""
        user = current_user
        if user.role != 'jobseeker':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        direct_hires = DirectHire.query.filter_by(jobseeker_id=user.jobseeker.id).all()
        
        return render_template('my_hires.html',
                             direct_hires=direct_hires,
                             current_user=user)

    # ===== CHAT ROUTES =====

    @app.route('/chat')
    @login_required
    def chat_home():
        """Main chat interface for both employers and job seekers"""
        user = current_user
        
        # Get chat rooms for the current user
        if user.role == 'employer':
            chat_rooms = ChatRoom.query.filter_by(employer_id=user.employer.id)\
                .order_by(ChatRoom.last_message_at.desc()).all()
            # Get hired seekers for status indicators
            hired_seeker_ids = [hire.jobseeker_id for hire in DirectHire.query.filter_by(employer_id=user.employer.id).all()]
        else:
            chat_rooms = ChatRoom.query.filter_by(jobseeker_id=user.jobseeker.id)\
                .order_by(ChatRoom.last_message_at.desc()).all()
            hired_seeker_ids = []
        
        # Get the first room as current room (if any)
        current_room = chat_rooms[0] if chat_rooms else None
        messages = []
        
        if current_room:
            messages = ChatMessage.query.filter_by(room_id=current_room.id)\
                .order_by(ChatMessage.sent_at.asc()).all()
        
        return render_template('chat_room.html', 
                             user=user, 
                             chat_rooms=chat_rooms,
                             current_room=current_room,
                             messages=messages,
                             hired_seeker_ids=hired_seeker_ids)

    @app.route('/employer/chat')
    @login_required
    def employer_chat():
        """Employer-specific chat interface"""
        user = current_user
        if user.role != 'employer':
            flash('Access denied.', 'error')
            return redirect(url_for('dashboard'))
        
        # Get chat rooms for this employer
        chat_rooms = ChatRoom.query.filter_by(employer_id=user.employer.id)\
            .order_by(ChatRoom.last_message_at.desc()).all()
        
        # Get hired job seekers for status indicators
        hired_seeker_ids = [hire.jobseeker_id for hire in DirectHire.query.filter_by(employer_id=user.employer.id).all()]
        
        # Get current room (first one by default)
        current_room = chat_rooms[0] if chat_rooms else None
        messages = []
        
        if current_room:
            messages = ChatMessage.query.filter_by(room_id=current_room.id)\
                .order_by(ChatMessage.sent_at.asc()).all()
        
        return render_template('employer_chat.html',
                             user=user,
                             chat_rooms=chat_rooms,
                             current_room=current_room,
                             messages=messages,
                             hired_seeker_ids=hired_seeker_ids)

    @app.route('/chat/room/<int:room_id>')
    @login_required
    def chat_room(room_id):
        """Individual chat room"""
        user = current_user
        room = ChatRoom.query.get_or_404(room_id)
        
        # Verify user has access to this room
        if user.role == 'employer' and room.employer_id != user.employer.id:
            flash('Access denied.', 'error')
            return redirect(url_for('chat_home'))
        elif user.role == 'jobseeker' and room.jobseeker_id != user.jobseeker.id:
            flash('Access denied.', 'error')
            return redirect(url_for('chat_home'))
        
        # Get all chat rooms for sidebar
        if user.role == 'employer':
            chat_rooms = ChatRoom.query.filter_by(employer_id=user.employer.id)\
                .order_by(ChatRoom.last_message_at.desc()).all()
            hired_seeker_ids = [hire.jobseeker_id for hire in DirectHire.query.filter_by(employer_id=user.employer.id).all()]
        else:
            chat_rooms = ChatRoom.query.filter_by(jobseeker_id=user.jobseeker.id)\
                .order_by(ChatRoom.last_message_at.desc()).all()
            hired_seeker_ids = []
        
        # Get chat messages
        messages = ChatMessage.query.filter_by(room_id=room_id).order_by(ChatMessage.sent_at.asc()).all()
        
        # Mark messages as read
        for message in messages:
            if message.sender_id != user.id and not message.is_read:
                message.is_read = True
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking messages as read: {e}")
        
        return render_template('chat_room.html', 
                             room=room, 
                             messages=messages, 
                             user=user,
                             chat_rooms=chat_rooms,
                             current_room=room,
                             hired_seeker_ids=hired_seeker_ids)

    @app.route('/start_chat/<int:jobseeker_id>')
    @login_required
    def start_chat(jobseeker_id):
        """Start a new chat with a job seeker"""
        user = current_user
        if user.role != 'employer':
            flash('Only employers can start chats.', 'error')
            return redirect(url_for('dashboard'))
        
        jobseeker = JobSeeker.query.get_or_404(jobseeker_id)
        
        # Check if chat room already exists
        existing_room = ChatRoom.query.filter_by(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        ).first()
        
        if existing_room:
            return redirect(url_for('chat_room', room_id=existing_room.id))
        
        # Create new chat room
        new_room = ChatRoom(
            employer_id=user.employer.id,
            jobseeker_id=jobseeker_id
        )
        
        try:
            db.session.add(new_room)
            db.session.commit()
            return redirect(url_for('chat_room', room_id=new_room.id))
        except Exception as e:
            db.session.rollback()
            flash('Error starting chat.', 'error')
            return redirect(url_for('direct_hire'))

    @app.route('/start_chat_with_employer/<int:employer_id>')
    @login_required
    def start_chat_with_employer(employer_id):
        """Start a new chat with an employer (from job seeker side)"""
        user = current_user
        if user.role != 'jobseeker':
            flash('Only job seekers can start chats with employers.', 'error')
            return redirect(url_for('dashboard'))
        
        employer = Employer.query.get_or_404(employer_id)
        
        # Check if chat room already exists
        existing_room = ChatRoom.query.filter_by(
            employer_id=employer_id,
            jobseeker_id=user.jobseeker.id
        ).first()
        
        if existing_room:
            return redirect(url_for('chat_room', room_id=existing_room.id))
        
        # Create new chat room
        new_room = ChatRoom(
            employer_id=employer_id,
            jobseeker_id=user.jobseeker.id
        )
        
        try:
            db.session.add(new_room)
            db.session.commit()
            return redirect(url_for('chat_room', room_id=new_room.id))
        except Exception as e:
            db.session.rollback()
            flash('Error starting chat.', 'error')
            return redirect(url_for('dashboard'))

# ===== ENHANCED SOCKETIO HANDLERS =====

@socketio.on('connect')
def handle_connect():
    """Handle user connection to SocketIO"""
    try:
        if not current_user.is_authenticated:
            logger.warning("Unauthorized socket connection attempt")
            return False
        
        user = current_user
        emit('user_connected', {
            'user_id': user.id,
            'username': user.employer.employer_name if user.role == 'employer' else user.jobseeker.jobseeker_name,
            'message': 'Connected to chat'
        })
        logger.info(f"User {user.id} connected to socket")
        
    except Exception as e:
        logger.error(f"Error in handle_connect: {e}")
        return False

@socketio.on('join_room')
def handle_join_room(data):
    """Handle user joining a chat room"""
    try:
        room_id = data.get('room_id')
        user_id = current_user.id
        
        if not room_id:
            emit('error', {'message': 'Missing room ID'})
            return
        
        # Verify user has access to this room
        room = ChatRoom.query.get(room_id)
        if not room:
            emit('error', {'message': 'Chat room not found'})
            return
        
        # Check authorization
        if current_user.role == 'employer' and room.employer_id != current_user.employer.id:
            emit('error', {'message': 'Access denied to this chat room'})
            return
        elif current_user.role == 'jobseeker' and room.jobseeker_id != current_user.jobseeker.id:
            emit('error', {'message': 'Access denied to this chat room'})
            return
        
        join_room(str(room_id))
        
        # Get user display name
        username = current_user.employer.employer_name if current_user.role == 'employer' else current_user.jobseeker.jobseeker_name
        
        emit('user_joined', {
            'room_id': room_id,
            'user_id': user_id,
            'username': username
        }, room=str(room_id))
        
        logger.info(f"User {user_id} joined room {room_id}")
        
    except Exception as e:
        logger.error(f"Error in handle_join_room: {e}")
        emit('error', {'message': 'Failed to join room'})

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending messages with proper validation"""
    try:
        room_id = data.get('room_id')
        message_text = data.get('message', '').strip()
        
        # Validation
        if not room_id:
            emit('error', {'message': 'Missing room ID'})
            return
        
        if not message_text:
            emit('error', {'message': 'Message cannot be empty'})
            return
        
        if len(message_text) > 1000:
            emit('error', {'message': 'Message too long'})
            return
        
        # Verify room exists and user has access
        room = ChatRoom.query.get(room_id)
        if not room:
            emit('error', {'message': 'Chat room not found'})
            return
        
        # Verify authorization
        if current_user.role == 'employer' and room.employer_id != current_user.employer.id:
            emit('error', {'message': 'Access denied'})
            return
        elif current_user.role == 'jobseeker' and room.jobseeker_id != current_user.jobseeker.id:
            emit('error', {'message': 'Access denied'})
            return
        
        # Create and save message
        new_message = ChatMessage(
            room_id=room_id,
            sender_id=current_user.id,
            message=message_text
        )
        
        # Update room's last message time
        room.last_message_at = datetime.utcnow()
        
        db.session.add(new_message)
        db.session.commit()
        
        # Get sender name for display
        sender_name = current_user.employer.employer_name if current_user.role == 'employer' else current_user.jobseeker.jobseeker_name
        
        # Prepare message data for broadcasting
        message_data = {
            'id': new_message.id,
            'room_id': room_id,
            'sender_id': current_user.id,
            'sender_name': sender_name,
            'message': message_text,
            'sent_at': new_message.sent_at.isoformat(),
            'is_read': False
        }
        
        # Broadcast to room (including sender)
        emit('new_message', message_data, room=str(room_id))
        
        logger.info(f"Message sent in room {room_id} by user {current_user.id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in handle_send_message: {e}")
        emit('error', {'message': 'Failed to send message. Please try again.'})

@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicators"""
    try:
        room_id = data.get('room_id')
        if room_id and current_user.is_authenticated:
            username = current_user.employer.employer_name if current_user.role == 'employer' else current_user.jobseeker.jobseeker_name
            emit('user_typing', {
                'username': username,
                'user_id': current_user.id
            }, room=str(room_id), include_self=False)
    except Exception as e:
        logger.error(f"Error in handle_typing: {e}")

@socketio.on('stop_typing')
def handle_stop_typing(data):
    """Handle stop typing indicators"""
    try:
        room_id = data.get('room_id')
        if room_id:
            emit('user_stop_typing', {}, room=str(room_id), include_self=False)
    except Exception as e:
        logger.error(f"Error in handle_stop_typing: {e}")

@socketio.on('mark_messages_read')
def handle_mark_messages_read(data):
    """Mark messages as read"""
    try:
        room_id = data.get('room_id')
        if room_id and current_user.is_authenticated:
            # Mark all unread messages in this room as read (except user's own messages)
            unread_messages = ChatMessage.query.filter(
                ChatMessage.room_id == room_id,
                ChatMessage.sender_id != current_user.id,
                ChatMessage.is_read == False
            ).all()
            
            for message in unread_messages:
                message.is_read = True
            
            db.session.commit()
            
            emit('messages_read', {'room_id': room_id}, room=str(room_id))
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in handle_mark_messages_read: {e}")