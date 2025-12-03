from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField, FloatField, HiddenField
from wtforms.validators import DataRequired, Length, Regexp, Email, EqualTo, Optional, NumberRange, ValidationError
import re

def validate_password_strength(form, field):
    """Custom validator for password strength"""
    password = field.data
    
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long.')
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must contain at least one uppercase letter (A-Z).')
    
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must contain at least one lowercase letter (a-z).')
    
    if not re.search(r'[0-9]', password):
        raise ValidationError('Password must contain at least one number (0-9).')
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).')

class SeekerRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Regexp(r'^\d{10}$', message="Phone must be a 10-digit number")])
    aadhaar = StringField('Aadhaar Card Number', validators=[
        DataRequired(message="Aadhaar number is required"),
        Regexp(r'^\d{12}$', message="Aadhaar must be a 12-digit number")
    ])
    email = StringField('Email Address', validators=[Optional(), Email()])
    years_experience = IntegerField('Years of Experience', validators=[DataRequired(), NumberRange(min=0, max=50)])
    gender = SelectField('Gender', choices=[
        ('', 'Select Gender'),
        ('male', 'Male'), 
        ('female', 'Female'), 
        ('other', 'Other')
    ], validators=[DataRequired()])
    skills = SelectField('Skills', choices=[
        ('', 'Select your skill'),
        ('Cooking', 'Cooking'),
        ('Washing', 'Washing'),
        ('Babysitting', 'Babysitting'),
        ('Cleaning', 'Cleaning'),
        ('Driving', 'Driving'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        validate_password_strength
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    location = StringField('Location', validators=[
        DataRequired(), 
        Length(min=2, max=100, message="Location must be between 2 and 100 characters")
    ])
    submit = SubmitField('Register as Job Seeker')

class EmployerRegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    aadhaar = StringField('Aadhaar Card Number', validators=[
        DataRequired(message="Aadhaar number is required"),
        Regexp(r'^\d{12}$', message="Aadhaar must be a 12-digit number")
    ])
    company_name = StringField('Company Name', validators=[Optional(), Length(max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    phone = StringField('Phone', validators=[DataRequired(), Regexp(r'^\d{10}$', message="Phone must be a 10-digit number")])
    location = StringField('Location', validators=[
        DataRequired(), 
        Length(min=2, max=100, message="Location must be between 2 and 100 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        validate_password_strength
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register as Employer')

class LoginForm(FlaskForm):
    phone = StringField('Phone', validators=[
        DataRequired(), 
        Regexp(r'^\d{10}$', message="Phone must be a 10-digit number")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message="Password must be at least 6 characters long")
    ])
    submit = SubmitField('Login')

class JobForm(FlaskForm):
    title = StringField('Job Title', validators=[
        DataRequired(), 
        Length(min=3, max=100, message="Job title must be between 3 and 100 characters")
    ])
    description = TextAreaField('Job Description', validators=[
        DataRequired(), 
        Length(min=10, message="Description must be at least 10 characters long")
    ])
    pay = FloatField('Salary', validators=[
        DataRequired(), 
        NumberRange(min=0, message="Salary must be a positive number")
    ])
    location = StringField('Location', validators=[
        DataRequired(), 
        Length(min=2, max=100, message="Location must be between 2 and 100 characters")
    ])
    required_skills = SelectField(
        'Required Skills',
        choices=[
            ('', 'Select required skill'), 
            ('Cooking', 'Cooking'), 
            ('Washing', 'Washing'), 
            ('Babysitting', 'Babysitting'), 
            ('Cleaning', 'Cleaning'), 
            ('Driving', 'Driving'), 
            ('Other', 'Other')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Post Job')

class JobApplicationForm(FlaskForm):
    job_id = HiddenField('Job ID', validators=[DataRequired()])
    submit = SubmitField('Apply for Job')

class ReviewForm(FlaskForm):
    rating = SelectField(
        'Rating', 
        choices=[
            ('', 'Select Rating'),
            ('1', '⭐ (1) - Poor'),
            ('2', '⭐⭐ (2) - Fair'), 
            ('3', '⭐⭐⭐ (3) - Good'),
            ('4', '⭐⭐⭐⭐ (4) - Very Good'),
            ('5', '⭐⭐⭐⭐⭐ (5) - Excellent')
        ],
        validators=[DataRequired(message="Please select a rating")]
    )
    comment = TextAreaField('Review Comment', validators=[
        Optional(), 
        Length(max=500, message="Comment cannot exceed 500 characters")
    ])
    submit = SubmitField('Submit Review')

class JobSearchForm(FlaskForm):
    q = StringField('Search', validators=[Optional()])
    location = StringField('Location', validators=[Optional()])
    skill = SelectField('Skill', choices=[
        ('', 'All Skills'),
        ('Cooking', 'Cooking'),
        ('Washing', 'Washing'),
        ('Babysitting', 'Babysitting'),
        ('Cleaning', 'Cleaning'),
        ('Driving', 'Driving'),
        ('Other', 'Other')
    ], validators=[Optional()])
    min_salary = FloatField('Minimum Salary', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Search Jobs')