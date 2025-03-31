from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')
@app.route('/premierleague')
def premierleague():
    return render_template('premierleague.html')

@app.route('/bundesliga')
def bundesliga():
    return render_template('bundesliga.html')

if __name__ == '__main__':
    app.run(debug=True)