from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from flask_sqlalchemy import SQLAlchemy

# --- CONFIGURATION ---
app = Flask(__name__)
app.secret_key = 'naglulu'
# SQLite database file named 'ecommerce.db' in the instance folder
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False) # NOTE: For a real app, use hashed passwords!

    def __repr__(self):
        return f'<User {self.username}>'

class Bike(db.Model):
    # This table now replaces the static BIKES list
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Bike {self.name}>'

# --- INITIAL DATA SETUP ---

# Use a context to create tables and populate initial data
with app.app_context():
    db.create_all()

    # Populate bikes only if the table is empty
    if not Bike.query.first():
        INITIAL_BIKES = [
            {'name': 'Mountain Bike X-Pro', 'price': 899.99,
             'description': 'Tough and ready for any trail.',
             'image_url': 'https://via.placeholder.com/400x300.png?text=Mountain+Bike'},
            {'name': 'Road Bike Aero-200', 'price': 1250.00,
             'description': 'Lightweight and fast for the road.',
             'image_url': 'https://via.placeholder.com/400x300.png?text=Road+Bike'},
            {'name': 'City Commuter C-10', 'price': 450.50,
             'description': 'Comfortable and reliable for daily travel.',
             'image_url': 'https://via.placeholder.com/400x300.png?text=Commuter+Bike'},
            {'name': 'Gravel Grinder G-500', 'price': 1599.00,
             'description': 'Versatile bike built for both pavement and rugged backroads. Hydraulic brakes and wide tires.',
             'image_url': 'https://via.placeholder.com/400x300.png?text=Gravel+Bike'},
            {'name': 'Electric Urban Cruiser E-1', 'price': 2100.00,
             'description': 'Classic style with a modern electric assist. Perfect for effortless commuting.',
             'image_url': 'https://via.placeholder.com/400x300.png?text=E-Bike'}
        ]
        for bike_data in INITIAL_BIKES:
            bike = Bike(**bike_data)
            db.session.add(bike)
        db.session.commit()
        print("Initial bikes added to the database.")

# --- HELPER FUNCTIONS ---

def get_user_context():
    cart = session.get('cart', {})
    cart_size = sum(cart.values())
    return {
        'logged_in': session.get('logged_in', False),
        'username': session.get('username', 'Guest'),
        'cart_size': cart_size
    }


def get_cart_details(cart_data):
    detailed_cart = []
    total_price = 0

    # Get all bikes from the database in one query
    bike_ids = [int(i) for i in cart_data.keys() if i.isdigit()]
    if not bike_ids:
        return [], 0

    # Query all bikes in the cart
    bikes_in_cart = Bike.query.filter(Bike.id.in_(bike_ids)).all()
    bike_map = {bike.id: bike for bike in bikes_in_cart}

    for bike_id_str, quantity in cart_data.items():
        try:
            bike_id = int(bike_id_str)
        except ValueError:
            continue

        bike = bike_map.get(bike_id)

        if bike:
            subtotal = bike.price * quantity
            total_price += subtotal
            detailed_cart.append({
                'id': bike.id,
                'name': bike.name,
                'price': bike.price,
                'quantity': quantity,
                'subtotal': subtotal
            })

    return detailed_cart, total_price


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in or register to access the shop.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function

# --- ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if get_user_context()['logged_in']:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Both username and password are required.', 'danger')
        # Check database for existing username
        elif User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'warning')
        else:
            # Create a new user object and commit to the database
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('auth.html', form_type='register', **get_user_context())


@app.route('/login', methods=['GET', 'POST'])
def login():
    if get_user_context()['logged_in']:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Find user in the database
        user = User.query.filter_by(username=username).first()

        # Check if user exists AND password matches (In a real app, verify hashed password)
        if user and user.password == password:
            session['logged_in'] = True
            session['username'] = username
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth.html', form_type='login', **get_user_context())


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/')
def index():
    context = get_user_context()
    if not context['logged_in']:
        flash('Please log in or register to access the shop.', 'info')
        return redirect(url_for('login'))

    return render_template('index.html', shop_name="Gear Up Bikes", **context)


@app.route('/products')
@login_required
def products():
    # Fetch bikes from the database
    bikes_list = Bike.query.all()
    # Convert SQLAlchemy objects to dicts for template
    bikes_data = [{'id': b.id, 'name': b.name, 'price': b.price, 'description': b.description, 'image_url': b.image_url} for b in bikes_list]

    return render_template('products.html', bikes=bikes_data, **get_user_context())


@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    context = get_user_context()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        print("\n--- NEW CONTACT MESSAGE ---")
        print(f"From: {name} ({email})")
        print(f"User: {context['username']}")
        print(f"Message: {message}")
        print("---------------------------\n")

        flash('Thank you! Your message has been sent. We will respond soon.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html', **context)


@app.route('/add_to_cart/<int:bike_id>', methods=['POST'])
@login_required
def add_to_cart(bike_id):
    # Ensure the bike exists before adding to cart
    if not Bike.query.get(bike_id):
        flash("Invalid product ID.", 'danger')
        return redirect(url_for('products'))

    quantity = 1

    if 'cart' not in session:
        session['cart'] = {}

    bike_id_str = str(bike_id)
    session['cart'][bike_id_str] = session['cart'].get(bike_id_str, 0) + quantity

    flash(f"Item added to cart!", 'success')
    return redirect(url_for('products'))





@app.route('/cart')
@login_required
def view_cart():
    cart_data = session.get('cart', {})
    detailed_cart, total_price = get_cart_details(cart_data)

    context = get_user_context()

    return render_template('cart.html',
                           cart_items=detailed_cart,
                           total=total_price,
                           **context)


@app.route('/remove_from_cart/<int:bike_id>', methods=['POST'])
@login_required
def remove_from_cart(bike_id):
    bike_id_str = str(bike_id)
    cart = session.get('cart', {})

    if bike_id_str in cart:
        cart[bike_id_str] -= 1

        if cart[bike_id_str] <= 0:
            del cart[bike_id_str]
            # Must update session after modification
            session.modified = True
            flash("Item removed from cart.", 'info')
        else:
            # Must update session after modification
            session.modified = True
            flash("Quantity reduced by one.", 'warning')

    return redirect(url_for('view_cart'))


@app.route('/checkout')
@login_required
def checkout():
    if not session.get('cart'):
        flash("Your cart is empty!", 'danger')
        return redirect(url_for('products'))

    # In a real application, you would save the order to an 'Orders' table here.
    session.pop('cart', None)
    session.modified = True

    flash("Checkout successful! Thank you for your order.", 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)