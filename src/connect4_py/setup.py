from setuptools import setup

package_name = 'connect4_py'

setup(
    name=package_name,
    version='0.0.0',
    py_modules=['GUI_node'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='enriques',
    maintainer_email='enrique.santos@student.uts.edu.au',
    description='Connect 4 ROS 2 Python GUI package',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'connect4_node = GUI_node:main',
        ],
    },
)