from setuptools import setup, find_packages

with open('script_readme.rst', encoding='UTF-8') as f:
    readme = f.read()

setup(
    name='python-vm-category-list',
    version='0.1',
    description='List VMs that are not assigned to any category.',
    long_description=readme,
    author='<your_name_here>',
    author_email='<your_email_address_here>',
    install_requires=[
        'requests',
        'urllib3'
    ],
    packages=find_packages('.'),
    package_dir={'': '.'}
)