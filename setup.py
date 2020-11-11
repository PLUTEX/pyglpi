from setuptools import setup

setup(
    name='pyglpi',
    use_scm_version=True,
    description='Thin wrapper around and helper functions for the GLPI REST API',
    author='Jan-Philipp Litza',
    author_email='jpl@plutex.de',
    license='BSD-2',
    packages=['pyglpi'],
    install_requires=[
        'hammock',
    ],
    testsuite='pyglpi.tests',
)
