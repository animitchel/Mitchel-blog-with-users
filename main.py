import os
import smtplib

from datetime import date
from functools import wraps

from dotenv import load_dotenv
from flask import abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor

from flask_login import login_user, LoginManager, current_user, logout_user, login_required

from models import BlogPost, User, Comment, db, app
from apis_buffer import news_api

from urllib3.exceptions import HTTPError
from werkzeug.security import generate_password_hash, check_password_hash

from forms import CreatePostForm, RegisterForm, LoginForm, CommentsForm, SearchForm

NUMS_OF_ARTICLES_TO_RENDER = 20
SMTPLIB_CONNECT_NO = 587
SALT_LENGTH = 10

# Load environment variables from .env file
load_dotenv()

# Set the secret key for secure session management
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")

# Initialize CKEditor for rich text editing
ckeditor = CKEditor(app)

# Initialize Bootstrap for styling
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.session_protection = "strong"
login_manager.login_view = "login"  # Set the login view for Flask-Login
login_manager.login_message_category = "info"
login_manager.init_app(app)


@login_manager.user_loader
def loader_user(user_id):
    """
    Load a user from the database based on the provided user ID.

    Args:
        user_id (str): The user ID to be loaded.

    Returns:
        User: The User object corresponding to the provided user ID, or None if not found.
    """
    # Load the user from the database using the provided user ID
    return db.session.get(User, int(user_id))


# Python Decorator
def admin(func):
    """
    Decorator that restricts access to the wrapped function to users with an ID less than or equal to 1.

    Args:
        func (function): The function to be decorated.

    Returns:
        function: The decorated function.

    Raises:
        werkzeug.exceptions.Forbidden: If the current user's ID is greater than 1, indicating insufficient privileges.
    """

    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if the current user's ID is greater than 1 (indicating insufficient privileges)
        if current_user.id > 1:
            # If the condition is met, abort the request with a 403 Forbidden status
            return abort(403)

        # If the condition is not met, proceed to the wrapped function
        return func(*args, **kwargs)

    return decorated_function


@app.route('/register', methods=["GET", "POST"])
def register():
    # import the relevant func from the apis_buffer app
    from apis_buffer import form_data
    """
    Handles user registration.

    If the registration form is submitted and valid, it checks if the user already exists.
    If the user doesn't exist, a new user is created and added to the database.
    The user is then logged in, and they are redirected to the 'get_all_posts' route.
    If the user already exists, a flash message is displayed, and the user is redirected to the 'login' route.

    Returns:
        flask.Response: A rendered template for the registration page or a redirect response.
    """
    # Create an instance of the RegisterForm
    register_form = RegisterForm()

    # Check if the registration form is submitted and valid
    if register_form.validate_on_submit():

        form_data_api = form_data(email=register_form.email.data,
                                  password=register_form.password.data,
                                  name=register_form.name.data)

        # Check if a user with the provided email already exists
        user = User.query.filter_by(email=form_data_api["email"]).first()

        if not user:
            # If the user doesn't exist, hash the password and create a new user
            password = generate_password_hash(password=form_data_api["password"], method="pbkdf2:sha256",
                                              salt_length=SALT_LENGTH)
            new_user = User(email=form_data_api["email"], password=password, name=form_data_api["name"])
            db.session.add(new_user)
            db.session.commit()

            # Log in the new user
            user = User.query.filter_by(email=form_data_api["email"]).first()
            login_user(user)

            # Redirect to the 'get_all_posts' route after successful registration
            return redirect(url_for("get_all_posts"))
        else:
            # If the user already exists, display a flash message and redirect to the 'login' route
            flash("You've already signed up with that email. Please login instead.")
            return redirect(url_for("login"))

    # Render the registration form template
    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    # import the relevant func from the apis_buffer app
    from apis_buffer import form_data
    """
    Handles user login.

    If the login form is submitted and valid, it checks if a user with the provided email exists.
    If the user exists, it compares the provided password with the hashed password in the database.
    If the passwords match, the user is logged in and redirected to the 'get_all_posts' route.
    If the password is incorrect, a flash message is displayed.
    If the email does not exist, a flash message is displayed.

    Returns:
        flask.Response: A rendered template for the login page or a redirect response.
    """
    # Create an instance of the LoginForm
    login_form = LoginForm()

    # Check if the login form is submitted and valid
    if login_form.validate_on_submit():

        form_data_api = form_data(email=login_form.email.data, password=login_form.password.data)

        # Check if a user with the provided email exists
        user = User.query.filter_by(email=form_data_api["email"]).first()

        if user:
            # If the user exists, check if the provided password matches the hashed password
            if check_password_hash(pwhash=user.password, password=form_data_api["password"]):
                # If passwords match, log in the user and redirect to the 'get_all_posts' route
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                # If the password is incorrect, display a flash message
                flash("Password incorrect, please try again")
        else:
            # If the email does not exist, display a flash message
            flash("This email does not exist, please try again")

    # Render the login form template
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    """
    Logs out the current user by invoking the 'logout_user' function from Flask-Login.

    Redirects the user to the 'get_all_posts' route after successful logout.

    Returns:
        flask.Response: A redirect response to the 'get_all_posts' route.
    """
    # Invoke the 'logout_user' function to log out the current user
    logout_user()

    # Redirect the user to the 'get_all_posts' route after successful logout
    return redirect(url_for('get_all_posts'))


@app.route('/', methods=["GET", "POST"])
def get_all_posts():
    # import the relevant func from the apis_buffer app
    from apis_buffer import database_api_data_to_render, render_top_searches, add_new_search_item_to_general_db, \
        add_new_search_item_to_db, render_general_top_searches

    """
    Route for displaying all blog posts, handling search functionality, and rendering the main page.

    Returns:
        flask.Response: Rendered HTML template.
    """
    # Query all blog posts from the database and reverse the order
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    posts_reversed_list = posts[::-1]

    # Generate JSON data for each blog post
    generator_posts = database_api_data_to_render(posts_reversed_list)

    # Initialize the search form
    search = SearchForm()

    # Get top searches for the current user if authenticated
    if current_user.is_authenticated:
        top_searches = render_top_searches(current_user.id)
    else:
        top_searches = None

    # Handle form submission for search
    if search.validate_on_submit():
        # Add the search item to both general and user-specific databases
        add_new_search_item_to_general_db(search_name=search.search.data)

        if current_user.is_authenticated:
            add_new_search_item_to_db(search_name=search.search.data)

        # Redirect to search results page
        return redirect(url_for("search_results", data=search.search.data))

    # Render the total top searches for all users
    total_top_searches_result = render_general_top_searches()

    # Render the main page with blog posts, search form, and other relevant data
    return render_template("index.html", all_posts=generator_posts, search=search,
                           top_searches=top_searches, total_top_searches_result=total_top_searches_result)


@app.route("/search/<data>", methods=["GET", "POST"])
def search_results(data):
    """
    Route for displaying search results based on the provided search data.

    Args:
        data (str): The search data.

    Returns:
        flask.Response: Rendered HTML template.
    """
    try:
        # Attempt to fetch news articles based on the search data
        news = news_api(data)
        news_articles = news[:NUMS_OF_ARTICLES_TO_RENDER]
    except TypeError:
        # Handle errors if the search operation fails
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except IndexError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except HTTPError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    else:
        # Render the search results page with the retrieved news articles
        return render_template("search.html", news=news_articles, search_name_index=data.title())


@app.route("/<post_id>/page-2", methods=["GET", "POST"])
def new_api(post_id):
    """
    Route for displaying additional news articles based on the provided post_id.

    Args:
        post_id (str): The post_id used for fetching additional news articles.

    Returns:
        flask.Response: Rendered HTML template.
    """
    try:
        # Attempt to fetch additional news articles based on the post_id
        news = news_api(post_id)
        news_articles = news[NUMS_OF_ARTICLES_TO_RENDER:]
    except TypeError:
        # Handle errors if the news article retrieval fails
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except IndexError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except HTTPError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    else:
        # Render the template to display additional news articles
        return render_template("shownews.html", news=news_articles, search_name_index=post_id)


@app.route("/<post_id>/<post_search>")
def add_article_to_db(post_id, post_search):
    """
    Route for adding a selected news article to the database as a new blog post.

    Args:
        post_id (str): The title of the selected news article.
        post_search (str): The search term used to retrieve news articles.

    Returns:
        flask.Response: Redirects to the main page after adding the blog post to the database.
    """
    try:
        # Attempt to fetch news articles based on the provided search term
        news = news_api(post_search)
    except TypeError:
        # Handle errors if the news article retrieval fails
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except IndexError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    except HTTPError:
        flash("Something went wrong, please search for the article again")
        return redirect(url_for("get_all_posts"))
    else:
        # Iterate through the retrieved news articles to find the selected one
        for art in news:
            if art["title"] == post_id:
                # Add the selected news article as a new blog post to the database
                with app.app_context():
                    new_blog = BlogPost(
                        title=art["title"],
                        subtitle=art["description"],
                        author=current_user,
                        img_url=art["urlToImage"],
                        body=f"<a href='{art['url']}'>{art['url']}</a> "
                             f"<b><--Goto URL, copy the body of the News "
                             f"content, paste it in 'Edit Post' and summit"
                             f"</b>",
                        date=f"{date.today().strftime('%B')} {date.today().day}, {date.today().year}"
                    )
                    db.session.add(new_blog)
                    db.session.commit()
                # Redirect to the main page after adding the blog post to the database
                return redirect(url_for("get_all_posts"))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    # import the relevant func from the apis_buffer app
    from apis_buffer import comments_on_post_api, requested_blog_post, comments_on_post
    """
    Renders the individual blog post page with comments and handles comment submission.

    Args:
        post_id (int): The unique identifier of the blog post to display.

    Returns:
        str: The HTML content of the blog post-page.

    """
    # Fetch the requested blog post and convert it to a JSON response.
    requested_post = requested_blog_post(db.get_or_404(BlogPost, post_id))

    # Create an instance of the CommentsForm for handling comments.
    comment = CommentsForm()

    # Retrieve all comments from the database and reverse the order.
    comments = db.session.query(Comment)[::-1]

    # Convert comments to JSON format for rendering on the page.
    comments_json = comments_on_post_api(comments)

    # Filter comments that belong to the specified blog post.
    ins_list = [com for com in comments if post_id == com.blog_post_id]
    number_of_comments = len(ins_list)

    # Handle comment submission.
    if comment.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login or register an account to comment.")
            return redirect(url_for("register"))

        # Prepare comment data for storage in the database.
        add_comments = comments_on_post(comment_form=comment, post_id=post_id)

        # Check comment length and flash a message if it exceeds the limit.
        if len(add_comments["comment_posted"]) > 350:
            flash("Please keep your comment under 350 characters.")
        else:
            # Add the new comment to the database and redirect to the post-page.
            with app.app_context():
                new_comment = Comment(comments_posted=add_comments["comment_posted"],
                                      commenter=current_user,
                                      blog_post_id=add_comments["post_id"])
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for("show_post", post_id=post_id))

    # Render the blog post page with associated comments.
    return render_template("post.html", post=requested_post, form=comment,
                           comments=comments_json, count=number_of_comments)


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin
def add_new_post():
    # import the relevant func from the apis_buffer app
    from apis_buffer import add_new_post_edit_post_internal_api
    """
    Handles the creation of a new blog post.

    This route is accessible only to logged in users with admin privileges.
    Users can submit a form to create a new blog post.

    Returns:
        flask.Response: Redirects to the main page after successfully adding a new post.

    """
    # Create a form for creating a new blog post.
    blog_form = CreatePostForm()

    # Check if the form is submitted and valid.
    if blog_form.validate_on_submit():
        # Convert the form data to a JSON response.
        blog = add_new_post_edit_post_internal_api(blog_form)

        # Create a new BlogPost instance with data from the JSON response.
        with app.app_context():
            new_blog = BlogPost(title=blog["title"], subtitle=blog["subtitle"],
                                author=current_user,
                                img_url=blog["img_url"], body=blog["body"],
                                date=blog["date"])
            db.session.add(new_blog)
            db.session.commit()

        # Redirect to the main page after adding the new post.
        return redirect(url_for("get_all_posts"))

    # Render the form for creating a new blog post.
    return render_template("make-post.html", form=blog_form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin
def edit_post(post_id):
    # import the relevant func from the apis_buffer app
    from apis_buffer import edit_post_internal_api, add_new_post_edit_post_internal_api
    """
    View function for editing a blog post.

    Args:
        post_id (int): The ID of the blog post to be edited.

    Returns:
        render_template: Renders the edit post-template with the form filled with existing data.

    """
    # Retrieve the existing blog post instance from the database
    ins_blog = db.get_or_404(BlogPost, post_id)
    # Convert the blog post instance to a JSON response for internal API use
    ins_blog_json = edit_post_internal_api(ins_blog)

    # Create a blog form instance
    blog_form = CreatePostForm()

    if blog_form.validate_on_submit():
        # If the form is submitted and validated, update the blog post instance with new data
        blog = add_new_post_edit_post_internal_api(blog_form)
        ins_blog.title = blog["title"]
        ins_blog.subtitle = blog["subtitle"]
        ins_blog.img_url = blog["img_url"]
        ins_blog.body = blog["body"]
        db.session.commit()
        # Redirect to the post-page after editing
        return redirect(url_for("show_post", post_id=post_id))

    # Fill the form with existing data for editing
    blog_form.title.data = ins_blog_json["title"]
    blog_form.subtitle.data = ins_blog_json["subtitle"]
    blog_form.img_url.data = ins_blog_json["img_url"]
    blog_form.body.data = ins_blog_json["body"]
    # Render the edit post-template with the form and set is_edit to True
    return render_template("make-post.html", form=blog_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin
def delete_post_and_comments(post_id):
    """
    View function for deleting a blog post and its associated comments.

    Args:
        post_id (int): The ID of the blog post to be deleted.

    Returns:
        redirect: Redirects to the page displaying all blog posts after deletion.

    """
    # Query all comments from the database
    comments = db.session.query(Comment)
    # Iterate through comments to find and delete those associated with the specified blog post
    for blog_comment in comments:
        if post_id == blog_comment.blog_post_id:
            db.session.delete(blog_comment)
            db.session.commit()

    # Retrieve the blog post instance to be deleted
    post_to_delete = db.get_or_404(BlogPost, post_id)
    # Delete the blog post from the database
    db.session.delete(post_to_delete)
    db.session.commit()

    # Redirect to the page displaying all blog posts after deletion
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    """
    View function for rendering the 'about' page.

    Returns:
        render_template: Renders the 'about.html' template.

    """
    # Render the 'about.html' template when the '/about' route is accessed
    return render_template("about.html")


def send_message(name, email, phone, message) -> None:
    """
    Send a message via email using SMTP.

    Args:
        name (str): Sender's name.
        email (str): Sender's email address.
        phone (str): Sender's phone number.
        message (str): The message content.

    Returns:
        None

    """
    # Connect to the SMTP server (Gmail in this case)
    with smtplib.SMTP("smtp.gmail.com", SMTPLIB_CONNECT_NO) as connection:
        # Start TLS encryption for secure communication
        connection.starttls()

        # Login to the email account
        connection.login(user='jeremylawrence112@gmail.com', password=os.getenv("PASSWORD"))

        # Send the email message
        connection.sendmail(from_addr='jeremylawrence112@gmail.com',
                            to_addrs='animitchel24@gmail.com',
                            msg=f"Subject:Mitchel's Blog!\n\n "
                                f"Name: {name}\n\n "
                                f"Email: {email}\n\n "
                                f"Phone: {phone}\n\n "
                                f"Message: {message.encode('utf-8')}")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    """
    Handle the contact form submission.

    If the request method is POST, extract form data and send a message.
    Display a confirmation message on successful submission.

    Returns:
        str: Rendered HTML template.

    """
    if request.method == "POST":
        # Extract form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')

        # Send the message
        send_message(name, email, phone, message)

        # Set a flag to indicate that the message has been sent
        sent = True

        # Render the template with the flag
        return render_template("contact.html", msg_sent=sent)

    # Render the contact form template for GET requests
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False)
