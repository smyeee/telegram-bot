from ftplib import FTP

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
