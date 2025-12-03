from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add missing columns to users table
    op.add_column('users', sa.Column('years_experience', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('gender', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('email', sa.String(length=100), nullable=True))
    
    # Create profiles table
    op.create_table('profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('location', sa.String(length=100), nullable=False),
        sa.Column('skills', sa.String(length=200), nullable=True),
        sa.Column('years_experience', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('profiles')
    op.drop_column('users', 'email')
    op.drop_column('users', 'gender')
    op.drop_column('users', 'years_experience')