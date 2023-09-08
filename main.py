from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentsForm

'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''
app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy()
db.init_app(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.session_protection = "strong"
login_manager.login_view = "login"
login_manager.login_message_category = "info"
login_manager.init_app(app)


@login_manager.user_loader
def loader_user(user_id):
    return db.session.get(User, int(user_id))


# CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Integer, nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commenter")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=True)
    subtitle = db.Column(db.String(250), nullable=True)
    date = db.Column(db.String(250), nullable=True)
    body = db.Column(db.Text, nullable=True)
    img_url = db.Column(db.String(250), nullable=True)


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    commenter_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    commenter = relationship("User", back_populates="comments")
    blog_post_id = db.Column(db.Integer)
    comments_posted = db.Column(db.Text)


# TODO: Create a User table for all your registered users.


with app.app_context():
    # db.drop_all()
    db.create_all()


# with app.app_context():
#     user = db.session.query(Comment)
#     for user in user:
#         if user.blog_post_id == 4:
#             # userr = db.get_or_404(User, user.commenter_id)
#             print(f"{user.commenter.name} = {user.comments_posted} ")
# print(user.name)
# for post in user.comments:
#     if post.blog_post_id == 4:
#         # print(post.blog_post_id)
#         print(post.comments_posted)

# Python Decorator
def login_require(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id > 2:
            # return redirect(url_for('get_all_posts'))
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        user = User.query.filter_by(email=register_form.email.data).first()
        if not user:
            password = generate_password_hash(password=register_form.password.data, method="pbkdf2:sha256",
                                              salt_length=10)
            new_user = User(email=register_form.email.data, password=password, name=register_form.name.data)
            db.session.add(new_user)
            db.session.commit()
            user = User.query.filter_by(email=register_form.email.data).first()
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("You've already signed up, with that Email, Login instead")
            return redirect(url_for("login"))
    return render_template("register.html", form=register_form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if user:
            if check_password_hash(pwhash=user.password, password=login_form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Password incorrect, please try again")
        else:
            flash("This Email does not exist, please try again")

    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment = CommentsForm()
    gravatar = Gravatar(app,
                        size=100,
                        rating='g',
                        default='retro',
                        force_default=False,
                        force_lower=False,
                        use_ssl=False,
                        base_url=None)
    users = db.session.query(Comment)
    if comment.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login or register an account with us to be able to comment")
            return redirect(url_for("register"))
        with app.app_context():
            new_comment = Comment(comments_posted=comment.comment.data, commenter=current_user, blog_post_id=post_id)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
    return render_template("post.html", post=requested_post, form=comment, users=users, gravatar=gravatar)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@login_required
@login_require
def add_new_post():
    blog_form = CreatePostForm()
    if blog_form.validate_on_submit():
        with app.app_context():
            new_blog = BlogPost(title=blog_form.title.data, subtitle=blog_form.subtitle.data,
                                author=current_user,
                                img_url=blog_form.img_url.data, body=blog_form.body.data,
                                date=f"{date.today().strftime('%B')} {date.today().day}, {date.today().year}")
            db.session.add(new_blog)
            db.session.commit()

        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=blog_form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@login_require
def edit_post(post_id):
    ins_blog = db.get_or_404(BlogPost, post_id)
    blog_form = CreatePostForm()

    if blog_form.validate_on_submit():
        ins_blog.title = blog_form.title.data
        ins_blog.subtitle = blog_form.subtitle.data
        ins_blog.img_url = blog_form.img_url.data
        ins_blog.body = blog_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))

    blog_form.title.data = ins_blog.title
    blog_form.subtitle.data = ins_blog.subtitle
    blog_form.img_url.data = ins_blog.img_url
    blog_form.body.data = ins_blog.body
    return render_template("make-post.html", form=blog_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@login_require
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
