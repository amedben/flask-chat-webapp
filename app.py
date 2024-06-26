from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import os
from random import randint, randrange
import email_validator
import smtplib
from wtforms.fields.html5 import EmailField
import requests


app = Flask(__name__)
app.secret_key = os.urandom(24)

# Config MySQL
mysql = MySQL()
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'sslchat'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Config email

appemail = ""
apppass = ""
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login(appemail, apppass)

# Initialize the app for use with this MySQL class
mysql.init_app(app)




def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, *kwargs)
        else:
            flash('Unauthorized, Please logged in', 'danger')
            return redirect(url_for('login'))

    return wrap


def not_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            flash('Unauthorized, You logged in', 'danger')
            return redirect(url_for('index'))
        else:
            return f(*args, *kwargs)

    return wrap


@app.route('/')
def index():
    response = requests.get("https://quote-garden.herokuapp.com/api/v3/quotes/random")
    json_data = response.json()
    data = json_data['data']
    quote = data[0]['quoteText']

    return render_template('home.html',quote=quote)


class LoginForm(Form):  # Create Message Form
    username = StringField('Username', [validators.length(min=1)], render_kw={'autofocus': True})


# User Login
@app.route('/login', methods=['GET', 'POST'])
@not_logged_in
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        # GEt user form
        username = form.username.data
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username=%s", [username])

        if result > 0:
            # Get stored value
            data = cur.fetchone()
            password = data['password']
            uid = data['id']
            name = data['name']

            # Compare password
            if sha256_crypt.verify(password_candidate, password):
                # passed
                session['logged_in'] = True
                session['uid'] = uid
                session['s_name'] = name
                x = '1'
                cur.execute("UPDATE users SET online=%s WHERE id=%s", (x, uid))
                flash('You are now logged in', 'success')

                return redirect(url_for('index'))

            else:
                flash('Incorrect password', 'danger')
                return render_template('login.html', form=form)

        else:
            flash('Username not found', 'danger')
            # Close connection
            cur.close()
            return render_template('login.html', form=form)
    return render_template('login.html', form=form)


@app.route('/out')
def logout():
    if 'uid' in session:
        # Create cursor
        cur = mysql.connection.cursor()
        uid = session['uid']
        x = '0'
        cur.execute("UPDATE users SET online=%s WHERE id=%s", (x, uid))
        session.clear()
        flash('You are logged out', 'success')
        return redirect(url_for('index'))
    return redirect(url_for('login'))


class RegisterForm(Form):
    name = StringField('Name', [validators.length(min=3, max=50)], render_kw={'autofocus': True})
    username = StringField('Username', [validators.length(min=3, max=25)])
    email = EmailField('Email', [validators.DataRequired(), validators.Email(), validators.length(min=4, max=30)])
    password = PasswordField('Password', [validators.length(min=3)])

def usercheck(username):
    cur = mysql.connection.cursor()
    res = cur.execute("SELECT * FROM users WHERE username=%s", [username])
    return res

@app.route('/register', methods=['GET', 'POST'])
@not_logged_in
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        passworddum = form.password.data
        password = sha256_crypt.encrypt(str(form.password.data))
        res = usercheck(username)
        if (res == 0):
            # Create Cursor
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)",
                        (name, email, username, password))

            # Commit cursor
            mysql.connection.commit()

            # Close Connection
            cur.close()

            msgtxt = "You are registered on the web app your username is \t" + username + "\n  and your password is \t" + passworddum
            server.sendmail(appemail, email, msgtxt)
            flash('You are now registered and can login', 'success')
            server.close()
            return redirect(url_for('index'))
        else:
            flash('Username is already in use try again', 'danger')
    return render_template('register.html', form=form)


class MessageForm(Form):  # Create Message Form
    body = StringField('', [validators.length(min=1)], render_kw={'autofocus': True})


@app.route('/chatting/<string:id>', methods=['GET', 'POST'])
def chatting(id):
    if 'uid' in session:
        form = MessageForm(request.form)
        # Create cursor
        cur = mysql.connection.cursor()

        # lid name
        get_result = cur.execute("SELECT * FROM users WHERE id=%s", [id])
        l_data = cur.fetchone()
        if get_result > 0:
            session['name'] = l_data['name']
            uid = session['uid']
            session['lid'] = id

            if request.method == 'POST' and form.validate():
                txt_body = form.body.data
                # Create cursor
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO messages(body, msg_by, msg_to) VALUES(%s, %s, %s)",
                            (txt_body, id, uid))
                # Commit cursor
                mysql.connection.commit()

            # Get users
            cur.execute("SELECT * FROM users")
            users = cur.fetchall()

            # Close Connection
            cur.close()
            return render_template('chat_room.html', users=users, form=form)
        else:
            flash('No permission!', 'danger')
            return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))


@app.route('/chats', methods=['GET', 'POST'])
def chats():
    if 'lid' in session:
        id = session['lid']
        uid = session['uid']
        # Create cursor
        cur = mysql.connection.cursor()
        # Get message
        cur.execute("SELECT * FROM messages WHERE (msg_by=%s AND msg_to=%s) OR (msg_by=%s AND msg_to=%s) "
                    "ORDER BY id ASC", (id, uid, uid, id))
        chats = cur.fetchall()
        # Close Connection
        cur.close()
        return render_template('chats.html', chats=chats, )
    return redirect(url_for('login'))


@app.route('/test')
def test():
    form = PassresetForm(request.form)
    return render_template('update.html', form=form)


class PassresetForm(Form):  # Create Message Form
    username = StringField('Username', [validators.length(min=1)])


@app.route('/passreset', methods=['GET', 'POST'])
@not_logged_in
def passreset():
    form = PassresetForm(request.form)
    if request.method == 'POST' and form.validate():
        username = request.form['username']
        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username=%s", [username])
        if result > 0:
            # Get stored value
            data = cur.fetchone()
            email = data['email']
            id = data['id']
            global aa
            aa = str(randint(10000, 99999))
            print(aa)
            txtmsg = "your verification key is  " + str(aa)
            server.sendmail(appemail, email, txtmsg)
            return redirect(url_for('update', id=id))

        else:
            flash('Username not found', 'danger')
        # Close connection
        cur.close()
    return render_template('passreset.html', form=form)


@app.route('/passreset/<string:id>', methods=['GET', 'POST'])
def update(id):
    if request.method == 'POST':
        keyy = str(request.form['keyy'])
        if keyy == aa:
            password = sha256_crypt.encrypt(str(request.form['password']))
            cnx = mysql.connection
            cur = cnx.cursor()
            print(id)
            cur.execute("UPDATE users SET password=%s WHERE id=%s", (password, id))
            cnx.commit()
            flash('password changed', 'success')
            return redirect(url_for('login'))
        else:
            flash('wrong OTP!', 'danger')
    return render_template('update.html')


if __name__ == '__main__':
    app.run(debug=True)
