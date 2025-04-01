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

@app.route('/laliga')
def laliga():
    return render_template('laliga.html')

@app.route('/ligue1')
def ligue1():
    return render_template('ligue1.html')

@app.route('/seriea')
def seriea():
    return render_template('seriea.html')

@app.route('/eredivisie')
def eredivisie():
    return render_template('eredivisie.html')

@app.route('/scotishpremierleague')
def scotishpremierleague():
    return render_template('scotishpremierleague.html')

@app.route('/greecesuperleague')
def greecesuperleague():
    return render_template('greecesuperleague.html')
@app.route('/jupilerleague')
def jupilerleague():
    return render_template('jupilerleague.html')

@app.route('/superleauge')
def superleauge():
    return render_template('superleauge.html')

@app.route('/leaugeportugal')
def leaugeportugal():
    return render_template('leaugeportugal.html')

if __name__ == '__main__':
    app.run(debug=True)