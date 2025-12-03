# models.py - Complete version with all required methods
from app import db
from flask_login import UserMixin
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'employer' or 'jobseeker'
    aadhaar_number = db.Column(db.String(12), unique=True, nullable=False)
    
    # Relationships
    employer = db.relationship('Employer', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    jobseeker = db.relationship('JobSeeker', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='reviewer', lazy=True, cascade='all, delete-orphan')
    reviews_received = db.relationship('Review', foreign_keys='Review.reviewee_id', backref='reviewee', lazy=True, cascade='all, delete-orphan')
    sent_messages = db.relationship('ChatMessage', foreign_keys='ChatMessage.sender_id', backref='sender', lazy=True, cascade='all, delete-orphan')

    # Add these methods for Flask-Login
    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_display_name(self):
        """Get display name based on role"""
        if self.role == 'employer' and self.employer:
            return self.employer.employer_name
        elif self.role == 'jobseeker' and self.jobseeker:
            return self.jobseeker.jobseeker_name
        return "Unknown User"


class Employer(db.Model):
    __tablename__ = 'employers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    employer_name = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    
    # NEW: Add geolocation fields for Employer
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Relationships
    jobs = db.relationship('Job', backref='employer', lazy=True, cascade='all, delete-orphan')
    direct_hires = db.relationship('DirectHire', backref='employer', lazy=True, cascade='all, delete-orphan')
    chat_rooms = db.relationship('ChatRoom', backref='employer', lazy=True, cascade='all, delete-orphan')

    def get_hired_seeker_ids(self):
        """Get list of job seeker IDs hired by this employer"""
        try:
            hired_seeker_ids = []
            
            # Get direct hires by this employer
            direct_hires = DirectHire.query.filter_by(employer_id=self.id).all()
            for hire in direct_hires:
                if hire.jobseeker_id not in hired_seeker_ids:
                    hired_seeker_ids.append(hire.jobseeker_id)
            
            # Also get job seekers hired through applications
            hired_applications = Application.query.filter(
                Application.job.has(employer_id=self.id),
                Application.status == 'hired'
            ).all()
            for app in hired_applications:
                if app.jobseeker_id not in hired_seeker_ids:
                    hired_seeker_ids.append(app.jobseeker_id)
            
            return hired_seeker_ids
        except Exception as e:
            return []

    def get_total_hires(self):
        """Get total number of job seekers hired by this employer"""
        try:
            direct_hires_count = DirectHire.query.filter_by(employer_id=self.id).count()
            
            application_hires_count = Application.query.filter(
                Application.job.has(employer_id=self.id),
                Application.status == 'hired'
            ).count()
            
            return direct_hires_count + application_hires_count
        except Exception as e:
            return 0

    def get_active_jobs_count(self):
        """Get count of active jobs posted by this employer"""
        try:
            return Job.query.filter_by(employer_id=self.id).count()
        except Exception as e:
            return 0

    def get_average_rating(self):
        """Get average rating for this employer"""
        try:
            reviews = Review.query.filter_by(reviewee_id=self.user_id).all()
            if not reviews:
                return 0
            total_rating = sum(review.rating for review in reviews)
            return round(total_rating / len(reviews), 1)
        except Exception as e:
            return 0


class JobSeeker(db.Model):
    __tablename__ = 'jobseekers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    jobseeker_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    skills = db.Column(db.String(200))
    years_experience = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    location = db.Column(db.String(100), nullable=False)
    
    # NEW: Geolocation fields
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Relationships
    applications = db.relationship('Application', backref='jobseeker', lazy=True, cascade='all, delete-orphan')
    direct_hires = db.relationship('DirectHire', backref='jobseeker', lazy=True, cascade='all, delete-orphan')
    chat_rooms = db.relationship('ChatRoom', backref='jobseeker', lazy=True, cascade='all, delete-orphan')

    def get_hired_employer_ids(self):
        """Get list of employer IDs who have hired this job seeker"""
        try:
            hired_employer_ids = []
            
            # Get direct hires for this job seeker
            direct_hires = DirectHire.query.filter_by(jobseeker_id=self.id).all()
            for hire in direct_hires:
                if hire.employer_id not in hired_employer_ids:
                    hired_employer_ids.append(hire.employer_id)
            
            # Also get employers who hired through applications
            hired_applications = Application.query.filter_by(
                jobseeker_id=self.id, 
                status='hired'
            ).all()
            for app in hired_applications:
                employer_id = app.job.employer_id
                if employer_id not in hired_employer_ids:
                    hired_employer_ids.append(employer_id)
            
            return hired_employer_ids
        except Exception as e:
            return []

    def get_hired_employers(self):
        """Get list of employers who have hired this job seeker"""
        try:
            employer_ids = self.get_hired_employer_ids()
            if not employer_ids:
                return []
            
            return Employer.query.filter(Employer.id.in_(employer_ids)).all()
        except Exception as e:
            return []

    def get_total_hires(self):
        """Get total number of times this job seeker has been hired"""
        try:
            direct_hires_count = DirectHire.query.filter_by(jobseeker_id=self.id).count()
            
            application_hires_count = Application.query.filter_by(
                jobseeker_id=self.id, 
                status='hired'
            ).count()
            
            return direct_hires_count + application_hires_count
        except Exception as e:
            return 0

    def get_applications_count(self):
        """Get total number of job applications submitted"""
        try:
            return Application.query.filter_by(jobseeker_id=self.id).count()
        except Exception as e:
            return 0

    def get_pending_applications_count(self):
        """Get number of pending applications"""
        try:
            return Application.query.filter_by(jobseeker_id=self.id, status='pending').count()
        except Exception as e:
            return 0

    def get_average_rating(self):
        """Get average rating for this job seeker"""
        try:
            reviews = Review.query.filter_by(reviewee_id=self.user_id).all()
            if not reviews:
                return 0
            total_rating = sum(review.rating for review in reviews)
            return round(total_rating / len(reviews), 1)
        except Exception as e:
            return 0

    def get_skills_list(self):
        """Get skills as a list"""
        try:
            if self.skills:
                return [skill.strip() for skill in self.skills.split(',')]
            return []
        except Exception as e:
            return []


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('employers.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    pay = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    required_skills = db.Column(db.String(200), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Geolocation fields
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Relationships
    applications = db.relationship('Application', backref='job', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='job', lazy=True, cascade='all, delete-orphan')

    def get_applications_count(self):
        """Get total number of applications for this job"""
        try:
            return Application.query.filter_by(job_id=self.id).count()
        except Exception as e:
            return 0

    def get_pending_applications_count(self):
        """Get number of pending applications"""
        try:
            return Application.query.filter_by(job_id=self.id, status='pending').count()
        except Exception as e:
            return 0

    def get_hired_applications_count(self):
        """Get number of hired applications"""
        try:
            return Application.query.filter_by(job_id=self.id, status='hired').count()
        except Exception as e:
            return 0

    def is_applied_by(self, jobseeker_id):
        """Check if a job seeker has applied for this job"""
        try:
            application = Application.query.filter_by(
                job_id=self.id, 
                jobseeker_id=jobseeker_id
            ).first()
            return application is not None
        except Exception as e:
            return False

    def get_required_skills_list(self):
        """Get required skills as a list"""
        try:
            if self.required_skills:
                return [skill.strip() for skill in self.required_skills.split(',')]
            return []
        except Exception as e:
            return []

    def get_days_since_posted(self):
        """Get number of days since job was posted"""
        try:
            delta = datetime.utcnow() - self.posted_at
            return delta.days
        except Exception as e:
            return 0


class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey('jobseekers.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, hired, rejected
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_status_badge_class(self):
        """Get Bootstrap badge class based on status"""
        status_classes = {
            'pending': 'bg-warning',
            'hired': 'bg-success',
            'rejected': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')

    def get_status_text(self):
        """Get display text for status"""
        status_texts = {
            'pending': 'Pending',
            'hired': 'Hired',
            'rejected': 'Rejected'
        }
        return status_texts.get(self.status, 'Unknown')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_rating_stars(self):
        """Get HTML for rating stars"""
        stars = ''
        for i in range(1, 6):
            if i <= self.rating:
                stars += '<i class="fas fa-star text-warning"></i>'
            else:
                stars += '<i class="far fa-star text-warning"></i>'
        return stars

    def get_reviewer_name(self):
        """Get reviewer's display name"""
        try:
            if self.reviewer.role == 'employer' and self.reviewer.employer:
                return self.reviewer.employer.employer_name
            elif self.reviewer.role == 'jobseeker' and self.reviewer.jobseeker:
                return self.reviewer.jobseeker.jobseeker_name
            return "Unknown User"
        except Exception as e:
            return "Unknown User"

    def get_reviewee_name(self):
        """Get reviewee's display name"""
        try:
            if self.reviewee.role == 'employer' and self.reviewee.employer:
                return self.reviewee.employer.employer_name
            elif self.reviewee.role == 'jobseeker' and self.reviewee.jobseeker:
                return self.reviewee.jobseeker.jobseeker_name
            return "Unknown User"
        except Exception as e:
            return "Unknown User"


class DirectHire(db.Model):
    __tablename__ = 'direct_hires'
    
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('employers.id', ondelete='CASCADE'), nullable=False)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey('jobseekers.id', ondelete='CASCADE'), nullable=False)
    hired_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='hired')  # hired, completed, terminated
    
    def __repr__(self):
        return f'<DirectHire {self.employer.employer_name} -> {self.jobseeker.jobseeker_name}>'

    def get_status_badge_class(self):
        """Get Bootstrap badge class based on status"""
        status_classes = {
            'hired': 'bg-success',
            'completed': 'bg-info',
            'terminated': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')

    def get_status_text(self):
        """Get display text for status"""
        status_texts = {
            'hired': 'Hired',
            'completed': 'Completed',
            'terminated': 'Terminated'
        }
        return status_texts.get(self.status, 'Unknown')


class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('employers.id', ondelete='CASCADE'), nullable=False)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey('jobseekers.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    messages = db.relationship('ChatMessage', backref='room', lazy=True, cascade='all, delete-orphan')

    def get_last_message(self):
        """Get the last message in this chat room"""
        try:
            return ChatMessage.query.filter_by(room_id=self.id).order_by(ChatMessage.sent_at.desc()).first()
        except Exception as e:
            return None

    def get_unread_messages_count(self, user_id):
        """Get count of unread messages for a user"""
        try:
            return ChatMessage.query.filter(
                ChatMessage.room_id == self.id,
                ChatMessage.sender_id != user_id,
                ChatMessage.is_read == False
            ).count()
        except Exception as e:
            return 0

    def get_other_user(self, current_user):
        """Get the other user in the chat room"""
        try:
            if current_user.role == 'employer':
                return self.jobseeker
            else:
                return self.employer
        except Exception as e:
            return None

    def get_other_user_name(self, current_user):
        """Get the name of the other user in the chat room"""
        try:
            other_user = self.get_other_user(current_user)
            if other_user:
                if current_user.role == 'employer':
                    return other_user.jobseeker_name
                else:
                    return other_user.employer_name
            return "Unknown User"
        except Exception as e:
            return "Unknown User"


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_rooms.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<ChatMessage {self.id} from {self.sender_id}>'

    def get_sender_name(self):
        """Get sender's display name"""
        try:
            if self.sender.role == 'employer' and self.sender.employer:
                return self.sender.employer.employer_name
            elif self.sender.role == 'jobseeker' and self.sender.jobseeker:
                return self.sender.jobseeker.jobseeker_name
            return "Unknown User"
        except Exception as e:
            return "Unknown User"

    def is_own_message(self, current_user_id):
        """Check if the message was sent by the current user"""
        return self.sender_id == current_user_id

    def get_formatted_time(self):
        """Get formatted time for display"""
        try:
            return self.sent_at.strftime('%H:%M')
        except Exception as e:
            return "00:00"


# Location Service Model
class LocationService:
    @staticmethod
    def get_coordinates(location_name):
        """Get latitude and longitude from location name using geocoding"""
        try:
            # You can use Google Geocoding API, OpenStreetMap Nominatim, or other services
            # For now, we'll use a simple mock - replace with actual geocoding service
            import random
            # Mock coordinates for demonstration
            return {
                'latitude': 19.8762 + random.uniform(-0.1, 0.1),
                'longitude': 75.3433 + random.uniform(-0.1, 0.1)
            }
        except Exception as e:
            print(f"Geocoding error: {e}")
            return {'latitude': None, 'longitude': None}

    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in kilometers using Haversine formula"""
        try:
            from math import radians, sin, cos, sqrt, atan2
            
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
        except Exception as e:
            print(f"Distance calculation error: {e}")
            return None