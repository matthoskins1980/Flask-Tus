"""
Flask-Tus
-------------

Implements the tus.io server-side file-upload protocol
visit http://tus.io for more information

"""
from setuptools import setup


setup(
    name='Flask-Tus',
    version='0.6.1',
    url='http://github.com/matthoskins1980/Flask-Tus/',
    license='MIT',
    author='Matt Hoskins',
    author_email='matt.hoski+flask-tus@gmail.com',
    description='TUS protocol implementation',
    long_description=__doc__,
    py_modules=['flask_tus'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
		'Redis'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
