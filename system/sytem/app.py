from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from functools import wraps
from datetime import datetime  # <-- This import is needed for orders

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # <-- Tells @login_required where to send users
login_manager.login_message_category = 'info'


# --- Models (Database Tables) ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(60), nullable=False)
    cart_items = db.relationship('CartItem', backref='owner', lazy=True)

    # --- NEW ADMIN FIELDS ---
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    orders = db.relationship('Order', backref='user', lazy=True)


class Bike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(300), nullable=False)  # Will store 'bike-aero.jpg' etc.


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bike_id = db.Column(db.Integer, db.ForeignKey('bike.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    bike = db.relationship('Bike')


# --- NEW ORDER MODELS ---

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    order_items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    bike_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- NEW ADMIN DECORATOR ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('products'))
        return f(*args, **kwargs)

    return decorated_function


# --- Helper Function to Populate Products ---
def create_initial_products():
    # Check if bikes already exist
    if Bike.query.count() == 0:
        products = [
            Bike(name='Aero Road Bike',
                 price=2800.00,
                 description='From your "areoo.htm" file. A sleek, fast road bike built for speed and efficiency.',
                 image_url='bike-aero.jpg'),
            Bike(name='Surron E-Bike',
                 price=4500.00,
                 description='From your "cruiser.htm" file. A powerful and versatile electric bike.',
                 image_url='bike-surron.jpg'),
            Bike(name='Mountain Bike X9',
                 price=2100.00,
                 description='From your "x9.htm" file. A full-suspension mountain bike for demanding trails.',
                 image_url='bike-x9.jpg'),
            Bike(name='Electric Commuter',
                 price=1850.00,
                 description='From your "electric.htm" file. The perfect companion for your daily commute.',
                 image_url='bike-electric.jpg'),
            Bike(name='Gravel Bike',
                 price=1999.00,
                 description='From your "gravel.htm" file. Explore paths less traveled with this versatile bike.',
                 image_url='bike-gravel.jpg')
        ]

        for p in products:
            db.session.add(p)
        db.session.commit()
        print("Created 5 initial products.")


# --- Context Processor (Global Variables for Templates) ---
@app.context_processor
def inject_global_vars():
    cart_size = 0
    username = None
    if current_user.is_authenticated:
        username = current_user.username
        cart_size = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=current_user.id).scalar() or 0
    return dict(cart_size=cart_size, username=username)


# --- General Routes ---
@app.route('/')
def index():
    # The home page is now the login page.
    return redirect(url_for('login'))


@app.route('/products')
@login_required  # This page is now protected
def products():
    all_bikes = Bike.query.all()
    return render_template('products.html', bikes=all_bikes)


@app.route('/about')
def about():
    # This route is NOT protected, so anyone can see it.
    return render_template('about.html')


# --- Auth Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('products'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('products'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=True)

            # Send user to the shop after login
            return redirect(url_for('products'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))  # Send to login page after logout


# --- Cart Routes ---
@app.route('/add_to_cart/<int:bike_id>', methods=['POST'])
@login_required
def add_to_cart(bike_id):
    cart_item = CartItem.query.filter_by(user_id=current_user.id, bike_id=bike_id).first()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(user_id=current_user.id, bike_id=bike_id, quantity=1)
        db.session.add(cart_item)

    db.session.commit()
    flash('Item added to cart!', 'success')
    return redirect(url_for('products'))


@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = 0
    for item in cart_items:
        total += item.bike.price * item.quantity
    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/update_cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    new_quantity = request.form.get(f'quantity')
    if new_quantity:
        new_quantity = int(new_quantity)
        cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        if cart_item:
            if new_quantity <= 0:
                db.session.delete(cart_item)
                flash('Item removed from cart.', 'success')
            else:
                cart_item.quantity = new_quantity
                flash('Cart updated.', 'success')
            db.session.commit()
    return redirect(url_for('view_cart'))


# --- Checkout Route ---
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    # Use joinedload to get cart_items AND their related bike info in one query
    cart_items = CartItem.query.options(db.joinedload(CartItem.bike)).filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('view_cart'))

    total = sum(item.bike.price * item.quantity for item in cart_items)
    tax = total * 0.05
    grand_total = total + tax

    if request.method == 'POST':
        card_name = request.form.get('card_name')
        if not card_name:
            flash('Please fill in all payment details.', 'danger')
            return render_template('checkout.html', total=total, tax=tax, grand_total=grand_total)

        # --- UPDATED: Create Order History ---
        # 1. Create the main Order
        new_order = Order(user_id=current_user.id, total_price=grand_total)
        db.session.add(new_order)
        db.session.commit()  # Commit to get new_order.id

        # 2. Create OrderItems for each item in cart
        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                bike_name=item.bike.name,
                price=item.bike.price,
                quantity=item.quantity
            )
            db.session.add(order_item)

        # 3. Clear the cart
        for item in cart_items:
            db.session.delete(item)

        db.session.commit()  # Commit all changes

        flash('Payment successful! Thank you for your order.', 'success')
        return redirect(url_for('products'))

    return render_template('checkout.html', total=total, tax=tax, grand_total=grand_total)


# --- NEW ADMIN ROUTES ---

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/sales')
@login_required
@admin_required
def admin_sales():
    # Load orders, and eager-load the 'user' and 'order_items' relationships
    # to prevent N+1 queries in the template.
    orders = Order.query.options(
        db.joinedload(Order.user),
        db.joinedload(Order.order_items)
    ).order_by(Order.order_date.desc()).all()

    return render_template('admin_sales.html', orders=orders)


# --- Main Driver ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_initial_products()
    app.run(debug=True)