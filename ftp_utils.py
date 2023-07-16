from ftplib import FTP
import os
import datetime

def list_files(server: str, port: int, user: str, paswd: str) -> None:
    ftp = FTP()
    ftp.connect(server, port)
    ftp.login(user, paswd)
    print(ftp.nlst())


def upload(server: str, port: int, user: str, paswd: str, local_file_path: str, upload_name: str) -> None:
    ftp = FTP()
    ftp.connect(server, port)
    ftp.login(user, paswd)
    with open(local_file_path, 'rb') as f:
        ftp.storbinary(f"STOR {upload_name}", f)
    print(ftp.nlst())
    ftp.quit()


def download(server: str, port: int, user: str, paswd: str, local_file_path: str, remote_file: str) -> None:
    ftp = FTP()
    ftp.connect(server, port)
    ftp.login(user, paswd)
    with open(local_file_path, 'wb') as f:
        ftp.retrbinary(f"RETR {remote_file}", f.write)
    ftp.quit()


server = "ap2.peykasa.ir"
port = 21
user = "agri_weather"
paswd = "$Qq456"
today = datetime.datetime.now().strftime("%Y%m%d")
tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")

download(server, port, user, paswd, local_file_path=f"../pesteh{today}_1.geojson", remote_file=f"pesteh{today}_1.geojson")
download(server, port, user, paswd, local_file_path=f"../pesteh{tomorrow}_2.geojson", remote_file=f"pesteh{tomorrow}_2.geojson")