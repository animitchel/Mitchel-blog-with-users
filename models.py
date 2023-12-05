from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask import Flask
import os

# Create a Flask application instance
app = Flask(__name__)

# Connect to the database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///posts.db")
db = SQLAlchemy()
db.init_app(app)


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    """
    Represents a user in the application.

    Attributes:
        id (int): The unique identifier for the user.
        name (str): The name of the user.
        email (str): The email address of the user (unique).
        password (str): The hashed password of the user.
        posts (relationship): One-to-Many relationship with BlogPost model.
        comments (relationship): One-to-Many relationship with Comment model.
        top_search (relationship): One-to-Many relationship with TopSearches model.
    """
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commenter")
    top_search = relationship("TopSearches", back_populates="user_top_search")


class BlogPost(db.Model):
    """
    Represents a blog post in the application.

    Attributes:
        id (int): The unique identifier for the blog post.
        author_id (int): The foreign key referencing the author's user ID.
        author (relationship): Many-to-One relationship with User model.
        title (str): The title of the blog post (unique).
        subtitle (str): The subtitle or brief description of the blog post.
        date (str): The date when the blog post was created.
        body (str): The main content or body of the blog post.
        img_url (str): The URL of an image associated with the blog post.
    """
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=True)
    subtitle = db.Column(db.String(300), nullable=True)
    date = db.Column(db.String(250), nullable=True)
    body = db.Column(db.Text, nullable=True)
    img_url = db.Column(db.String(500), nullable=True)


class Comment(db.Model):
    """
    Represents a comment on a blog post in the application.

    Attributes:
        id (int): The unique identifier for the comment.
        commenter_id (int): The foreign key referencing the commenter's user ID.
        commenter (relationship): Many-to-One relationship with User model.
        blog_post_id (int): The ID of the associated blog post.
        comments_posted (str): The text content of the comment.
    """
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    commenter_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    commenter = relationship("User", back_populates="comments")
    blog_post_id = db.Column(db.Integer)
    comments_posted = db.Column(db.Text)


class TopSearches(db.Model):
    """
    Represents the top searches made by users in the application.

    Attributes:
        id (int): The unique identifier for the top search entry.
        user_id (int): The foreign key referencing the user who made the search.
        search_item (str): The item or query string that was searched.
        search_count (int): The count of how many times the search item was searched.
        user_top_search (relationship): Many-to-One relationship with the User model.
    """
    __tablename__ = "top_searches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    search_item = db.Column(db.String(300))
    search_count = db.Column(db.Integer)
    user_top_search = relationship("User", back_populates="top_search")


class TotalTopSearches(db.Model):
    """
    Represents the aggregated total searches made across all users in the application.

    Attributes:
        id (int): The unique identifier for the total top searches entry.
        search_item (str): The item or query string that was searched.
        total_search_count (int): The total count of how many times the search item was searched across all users.
    """
    __tablename__ = "total_top_searches"
    id = db.Column(db.Integer, primary_key=True)
    search_item = db.Column(db.String(300))
    total_search_count = db.Column(db.Integer)


with app.app_context():
    """
    Creates all the database tables defined in the application within the current application context.
    """
    db.create_all()
