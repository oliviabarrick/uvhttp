from setuptools import setup

setup(
    name='uvhttp',
    version='0.1',
    description='High performance Python HTTP client',
    url='https://codesink.net/justin/uvhttp',
    packages=['uvhttp'],
    install_requires=['uvloop==0.8.0','nose==1.3.7', 'httptools==0.0.9']
)
