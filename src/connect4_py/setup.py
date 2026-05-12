from setuptools import setup, find_packages

package_name = 'connect4_py'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='enriques',
    maintainer_email='enriques@todo.todo',
    description='Connect4 GUI package',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'connect4_node = connect4_py.GUI_node:main',
        ],
    },
)