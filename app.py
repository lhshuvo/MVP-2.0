import concurrent.futures
from flask import Flask, render_template, request, redirect, flash, send_from_directory
import pandas as pd
import requests
from werkzeug.utils import secure_filename
import os
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from tqdm import tqdm
import warnings
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './'
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['xlsx', 'xls']
@app.route('/', methods=['GET', 'POST'])
def myform():
    if request.method == 'POST':
        if 'x' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['x']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            df = pd.read_excel(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            responsess = []
            mail_validation = {}
            ua = UserAgent()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = []
                for i, row in df.iterrows():
                    email = str(row['DirectEmail'])
                    link = row['Source']
                    if pd.isna(email) or pd.isna(link):
                        mail_validation[i] = 0
                        responsess.append('')
                        continue
                    headers = {'User-Agent': ua.random}
                    futures.append(executor.submit(requests.get, link, headers=headers))
                for i, future in enumerate(tqdm(futures)):
                    try:
                        response = future.result()
                        if isinstance(response, requests.Response):
                            if response.status_code == 404:
                                mail_validation[i] = 0
                            else:
                                with warnings.catch_warnings():
                                    warnings.filterwarnings("ignore", category=Warning)
                                    soup = BeautifulSoup(response.content, 'html5lib')
                                text = soup.get_text()
                                if '@' in text:
                                    mail_validation[i] = 1
                                else:
                                    mail_validation[i] = 0
                            responsess.append(response)
                        elif isinstance(response, str):
                            mail_validation[i] = -1
                            responsess.append("Request Error")
                        else:
                            mail_validation[i] = 0
                            responsess.append('')
                    except requests.exceptions.RequestException:
                        mail_validation[i] = -1
                        responsess.append("Request Error")
            df["valid_email"] = pd.Series(mail_validation)
            df["Response_Type"] = pd.Series(responsess)
            filename1 = 'Outputfile.xlsx'
            df.to_excel(filename1)
            summary = {
                "total": len(df),
                "valid_emails": len(df.loc[df['valid_email'] == 1]),
                "invalid_emails": len(df.loc[df['valid_email'] == 0]),
                "request_errors": len(df.loc[df['valid_email'] == -1]),
            }
            return render_template('summary.html', summary=summary)
    return render_template('index.html')
@app.route('/download')
def download_file():
    return send_from_directory(app.config['UPLOAD_FOLDER'], 'Outputfile.xlsx', as_attachment=True)
if __name__ == '__main__':
    app.run(port=1234, debug=True)
