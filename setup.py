from setuptools import setup

setup(
    name='uvhttp',
    version='0.1',
    description='High performance Python HTTP client',
    url='https://codesink.net/justin/uvhttp',
    packages=['uvhttp'],
    install_requires=[ r.rstrip() for r in open('requirements.txt').readlines() ]
)
