VERIFY_TOKEN = "covid_info"

import requests
from flask import Flask, request
app = Flask(__name__)

# import thongtincovid19.scripts.postbot._site_updater as postbot
import _site_updater as postbot

@app.route('/webhook', methods=['GET'])
def handle_update_request():
    if (request.args.get('verify_token', '') == VERIFY_TOKEN):
        print("Verified")
        # return request.args.get('hub.challenge', '')
        return "Succeed"
    else:
        print("Wrong token")
        return "Error, wrong validation token ok"
        
@app.route('/webhook', methods=['POST'])
def handle_update_request_post():
    print(f"In Post: {request.args.get('verify_token', '')}")
    print(f"arg: {request.json}")
    if ('verify_token' in request.json and request.json['verify_token'] != None and request.json['verify_token'] == VERIFY_TOKEN):
        print("Verified")
        # return request.args.get('hub.challenge', '')
        res = postbot.run()
        return res
    else:
        print("Wrong token___")
        return "Error, wrong validation token in post"
    
if __name__ == "__main__":
    app.run(threaded=True, port=5000)