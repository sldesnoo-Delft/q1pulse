from setuptools import setup, find_packages

packages = ['q1pulse']
print('packages: {}'.format(packages))

setup(name="q1pulse",
	version="0.2",
    author="Sander de Snoo",
	packages = find_packages(),
	install_requires=[
        'qblox_instruments',
      ],
	)
