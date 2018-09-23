from setuptools import setup


setup(name='godaddy-ddns',
      version='0.2',
      description='DDNS-like update service for GoDaddy',
      url='http://github.com/N-Parsons/godaddy-ddns',
      author='Nathan Parsons',
      author_email='github@nparsons.uk',
      license='MIT',
      packages=['godaddy_ddns'],
      scripts=['bin/godaddy-ddns'],
      install_requires=[
          'pyyaml',
          'click',
          'pif',
          'godaddypy',
      ],
      zip_safe=False)
