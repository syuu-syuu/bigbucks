from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email
from flask import Blueprint, request, redirect, url_for, flash, render_template, current_app
from sqlalchemy.exc import IntegrityError
from bigbucks import database, login_manager
from bigbucks.model import User
from flask_login import login_user, current_user, login_required, logout_user
from bigbucks.historicals import update_portfolio_history_data, update_sp500_data

users_bp = Blueprint('users', __name__, template_folder='templates')

INITIAL_BALANCE = 1000000

# ---Configure Login_manager--- #


@login_manager.user_loader
# Retrieve the user object from the database using the user's ID loaded from the session.
def load_user(user_id):
    return User.query.get(int(user_id))


# Specify the login view to use when a user tries to access a protected page without being authenticated
login_manager.login_view = "users.login"


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[
                        DataRequired(), Email(), Length(min=6, max=120)])
    password = PasswordField('Password', validators=[
                             DataRequired(), Length(min=6, max=40)])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
                        DataRequired(), Email(), Length(min=6, max=100)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')


@users_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                new_user = User(form.username.data, form.email.data,
                                form.password.data)
                database.session.add(new_user)
                database.session.commit()
                formatted_balance = "${:,.2f}".format(INITIAL_BALANCE)
                flash(
                    f'Welcome to the beta version of Bigbucks, {new_user.username}! As a sign-up bonus, your account has been credited with a starting amount of {formatted_balance}.')

                return redirect(url_for('users.login'))

            except IntegrityError:
                database.session.rollback()
                flash(
                    f'ERROR! Email ({form.email.data}) already exists.', 'error')
        else:
            flash(f"Error in form data!", 'error')

    return render_template('register.html', form=form)


@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user is None:
                flash('This email address is not registered.', 'error')
                return render_template('login.html', form=form)
            elif not user.is_password_correct(form.password.data):
                flash('Incorrect password.', 'error')
                return render_template('login.html', form=form)
            else:
                login_user(user, remember=form.remember_me.data)
                flash(f'Thanks for logging in, {current_user.username}!')
                update_sp500_data()
                update_portfolio_history_data
                return redirect(url_for('home.index'))

    return render_template('login.html', form=form)


@users_bp.route('/logout')
@login_required
def logout():
    flash(f'Goodbye, {current_user.username}!')
    logout_user()
    return redirect(url_for('home.index'))


@users_bp.route('/delete_account', methods=['POST'])
def delete_account():
    user = User.query.get(current_user.id)
    database.session.delete(user)
    database.session.commit()
    return redirect(url_for('home.index'))


@users_bp.route("/profile", methods=['GET', 'POST'])
@login_required
def user_profile():
    users = None
    if current_user.is_admin:
        users = User.query.all()

    if request.method == 'POST':
        deposit_amount_str = request.form.get('deposit_amount')
        try:
            deposit_amount = float(deposit_amount_str)
            user = User.query.filter_by(id=current_user.id).first()
            updated_balance = user.account_balance + deposit_amount
            user.account_balance = updated_balance
            database.session.commit()

            flash(
                f'Congratulations! You have deposited ${deposit_amount:.2f} to your account. Your current balance is ${(user.account_balance):.2f}.', 'success')
            return redirect(url_for('users.user_profile'))
        except ValueError:
            flash('Error: Please enter a valid deposit amount.', 'error')
            return redirect(url_for("users.user_profile"))
        except OverflowError:
            flash('Sorry, the deposit value you entered is too large.', 'error')
            return redirect(url_for("users.user_profile"))

    return render_template('profile.html', balance=round(current_user.account_balance, 2))
