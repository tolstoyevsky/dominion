from setuptools import setup

setup(name='dominion',
      version='0.1',
      description='',
      url='https://bitbucket.org/cusdeb/dominion',
      author='CusDeb Team',
      maintainer='Evgeny Golyshev',
      maintainer_email='Evgeny Golyshev <eugulixes@gmail.com>',
      license='http://www.apache.org/licenses/LICENSE-2.0',
      packages=['dominion'],
      install_requires=[
          'celery',
      ])
