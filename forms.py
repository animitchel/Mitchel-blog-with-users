from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditorField


class CreatePostForm(FlaskForm):
    """
    Form for creating a new blog post.

    Attributes:
        title (StringField): Input field for the blog post title.
        subtitle (StringField): Input field for the blog post subtitle.
        img_url (StringField): Input field for the blog post image URL.
        body (CKEditorField): Input field for the blog post content.
        submit (SubmitField): Button to submit the blog post.
    """
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_url = StringField("Blog Image URL", validators=[DataRequired(), URL()])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class RegisterForm(FlaskForm):
    """
    Form for user registration.

    Attributes:
        email (StringField): Input field for user email.
        password (StringField): Input field for user password.
        name (StringField): Input field for username.
        submit (SubmitField): Button to submit the registration form.
    """
    email = StringField(label="Email", validators=[DataRequired()])
    password = StringField(label="Password", validators=[DataRequired()])
    name = StringField(label="Name", validators=[DataRequired()])
    submit = SubmitField(label="Signup")


class LoginForm(FlaskForm):
    """
    Form for user login.

    Attributes:
        email (StringField): Input field for user email.
        password (StringField): Input field for user password.
        submit (SubmitField): Button to submit the login form.
    """
    email = StringField(label="Email", validators=[DataRequired()])
    password = StringField(label="Password", validators=[DataRequired()])
    submit = SubmitField(label="Login")


class CommentsForm(FlaskForm):
    """
    Form for submitting comments on a blog post.

    Attributes:
        comment (CKEditorField): Input field for the comment content.
        submit (SubmitField): Button to submit the comment form.
    """
    comment = CKEditorField(validators=[DataRequired()])
    submit = SubmitField("Comment")


class SearchForm(FlaskForm):
    """
    Form for performing article searches.

    Attributes:
        search (StringField): Input field for the search query.
        submit (SubmitField): Button to submit the search form.
    """
    search = StringField(label="Search through millions of articles from over 80,000 large and small news sources and "
                               "blogs e.g Bitcoin", validators=[DataRequired()])
    submit = SubmitField("Search")
