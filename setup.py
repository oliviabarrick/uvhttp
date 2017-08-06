from setuptools import setup

setup(
    name='uvhttp',
    version='1.3',
    description='High performance Python HTTP client',
    url='https://github.com/justinbarrick/uvhttp',
    packages=['uvhttp'],
    install_requires=[ r.rstrip() for r in open('requirements.txt').readlines() ]
)
