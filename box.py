# coding: utf-8

from __future__ import unicode_literals
from boxsdk import JWTAuth, Client
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from conf import Configuration


DeclarativeBase = declarative_base()


class PhotoBoothInfo(DeclarativeBase):
    __tablename__ = 'photobooth_info'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)  # pylint:disable=invalid-name
    key = sqlalchemy.Column(sqlalchemy.String(45))
    value = sqlalchemy.Column(sqlalchemy.String(45))


class Box(object):
    _CLIENT_ID = Configuration.CLIENT_ID
    _CLIENT_SECRET = Configuration.CLIENT_SECRET
    _ENTERPRISE_ID = Configuration.ENTERPRISE_ID
    _PASSPHRASE = Configuration.PASSPHRASE

    def __init__(self):
        self._db_engine = sqlalchemy.create_engine('sqlite+pysqlite:///photobooth.db')
        self._session_maker = sessionmaker(bind=self._db_engine, autoflush=True)
        self._session = self._session_maker()
        DeclarativeBase.metadata.create_all(self._db_engine)

        self._auth = JWTAuth(
            client_id=self._CLIENT_ID,
            client_secret=self._CLIENT_SECRET,
            enterprise_id=self._ENTERPRISE_ID,
            rsa_private_key_file_sys_path='private_key.pem',
            rsa_private_key_passphrase=self._PASSPHRASE,
        )
        self._client = Client(self._auth)

        try:
            user_id = self._session.query(PhotoBoothInfo).filter_by(key='user_id').one().value
            from boxsdk.object.user import User
            self._upload_user = User(None, user_id)
        except NoResultFound:
            self._upload_user = self._client.create_user('Photobooth Uploader')
            self._session.add(PhotoBoothInfo(key='user_id', value=self._upload_user.object_id))
            self._session.commit()

        self._uploader_auth = JWTAuth(
            client_id=self._CLIENT_ID,
            client_secret=self._CLIENT_SECRET,
            enterprise_id=self._ENTERPRISE_ID,
            rsa_private_key_file_sys_path='private_key.pem',
            rsa_private_key_passphrase=self._PASSPHRASE,
        )
        self._uploader_auth.authenticate_app_user(self._upload_user)
        self._uploader = Client(self._uploader_auth)
        try:
            folder_id = self._session.query(PhotoBoothInfo).filter_by(key='folder_id').one().value
            self._folder = self._uploader.folder(folder_id)
        except NoResultFound:
            self._folder = self._uploader.folder('0').create_subfolder('Photobooth Images')
            self._session.add(PhotoBoothInfo(key='folder_id', value=self._folder.object_id))
            self._session.commit()

    def upload_photo(self, name, message, photo_sys_path):
        print 'uploading photo ', photo_sys_path, ' to box'
        photo = self._folder.upload(photo_sys_path)
        photo.metadata().create({
            'name': name,
            'message': message,
        })

    def download_photo(self, file_id, photo_sys_path):
        print 'downloading photo ', photo_sys_path, ' from box'
        with open(photo_sys_path, 'wb') as file_handle:
            self._client.file(file_id).download_to(file_handle)

    def list_files(self):
        return self._folder.get_items(1000)


if __name__ == '__main__':
    print Box()._folder.add_collaborator('jmeadows@box.com', 'editor')
