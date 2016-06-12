from flask import Flask, render_template, send_from_directory, current_app
from flask.ext.tus import tus_manager

import os

app = Flask(__name__)
tm = tus_manager(app, upload_url='/file-upload')

@tm.upload_file_handler
def upload_file_hander( upload_file_path, filename ):
    app = current_app

    app.logger.info( "doing something cool with {}, {}".format( upload_file_path, filename))
    return filename


@app.route("/")
def demo():
	return render_template("demo.html", upload_url = tm.upload_url )

# serve the uploaded files
@app.route('/uploads/<path:filename>', methods=['GET'])
def download(filename):
	uploads = os.path.join(app.root_path, tm.upload_folder)
	return send_from_directory(directory=uploads, filename=filename)

if __name__ == '__main__':
  app.run( host='0.0.0.0', debug=True )

