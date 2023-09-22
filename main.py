import os
import smtplib
import requests
from datetime import date
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from forms import CreatePostForm, RegisterForm, LoginForm, CommentsForm, SearchForm

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///posts.db")
db = SQLAlchemy()
db.init_app(app)

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
    password = db.Column(db.String(300), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commenter")


class BlogPost(db.Model):
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
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    commenter_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    commenter = relationship("User", back_populates="comments")
    blog_post_id = db.Column(db.Integer)
    comments_posted = db.Column(db.Text)


with app.app_context():
    db.create_all()


# Python Decorator
def admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id > 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


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


def news_api(search):
    header = {"X-Api-Key": os.getenv("APIKEY")
              }
    params = {
        "q": search,
        "language": "en",
        "sortBy": "publishedAt"
    }
    d = requests.get(url="https://newsapi.org/v2/everything?", params=params, headers=header)
    d.raise_for_status()
    data = d.json()
    return data["articles"][:10]


search_name = []


@app.route('/', methods=["GET", "POST"])
def get_all_posts():
    search_name.clear()
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    posts = posts[::-1]
    search = SearchForm()
    if search.validate_on_submit():
        search_name.append(search.search.data)
        return redirect(url_for("search_results", data=search.search.data))

    return render_template("index.html", all_posts=posts, search=search)


@app.route("/search/<data>", methods=["GET", "POST"])
def search_results(data):
    news = news_api(data)
    return render_template("search.html", news=news, search_name=data.title())


@app.route("/news-<post_id>", methods=["GET", "POST"])
def new_api(post_id):
    news = news_api(search_name[0])
    for data in news:
        if data["title"] == post_id:
            return render_template("shownews.html", news=data)


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
    comments = db.session.query(Comment)
    comments = comments[::-1]
    ins_list = [com for com in comments if post_id == com.blog_post_id]
    number_of_comments = len(ins_list)
    if comment.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login or register an account with us to be able to comment")
            return redirect(url_for("register"))
        with app.app_context():
            new_comment = Comment(comments_posted=comment.comment.data, commenter=current_user, blog_post_id=post_id)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
    return render_template("post.html", post=requested_post, form=comment, users=comments, gravatar=gravatar,
                           count=number_of_comments)


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin
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


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin
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


@app.route("/delete/<int:post_id>")
@admin
def delete_post(post_id):
    comment = db.session.query(Comment)
    for blog_comments in comment:
        if post_id == blog_comments.blog_post_id:
            db.session.delete(blog_comments)
            db.session.commit()

    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


def send_message(name, email, phone, message):
    with smtplib.SMTP("smtp.gmail.com", 587) as connection:
        connection.starttls()
        connection.login(user='jeremylawrence112@gmail.com', password=os.getenv("PASSWORD"))
        connection.sendmail(from_addr='jeremylawrence112@gmail.com',
                            to_addrs='animitchel24@gmail.com',
                            msg=f"Subject:Mitchel's Blog!\n\n "
                                f"Name: {name}\n\n "
                                f"Email: {email}\n\n "
                                f"Phone: {phone}\n\n "
                                f"Message: {message.encode('utf-8')}")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        send_message(request.form.get('name'), request.form.get('email'), request.form.get('phone'),
                     request.form.get('message'))

        sent = True
        return render_template("contact.html", msg_sent=sent)
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)
