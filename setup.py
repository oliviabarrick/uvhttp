from setuptools import setup
import os

requirements = os.path.join(os.path.dirname(__file__), 'requirements.txt')

setup(
    name='uvhttp',
    version='1.4',
    description='High performance Python HTTP client',
    url='https://github.com/justinbarrick/uvhttp',
    packages=['uvhttp'],
    install_requires=[ r.rstrip() for r in open(requirements).readlines() ]
)
