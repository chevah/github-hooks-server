# Build a minimal package for Azure.
mkdir -p build
cd build/
cp -r ../chevah .
rm -r chevah/__pycache__
cp -r ../config.ini .
cp -r ../config-secrets.ini .
rm -r chevah/github_hooks_server/__pycache__
rm -r chevah/github_hooks_server/tests
cp -r ../CONTRIBUTING.rst .
cp -r ../hook .
cp -r ../host.json .
cp -r ../LICENSE .
cp -r ../Makefile .
cp -r ../MANIFEST.in .
cp -r ../ping .
cp -r ../README.rst .
cp -r ../release-notes.rst .
cp -r ../requirements.txt .
cp -r ../scripts .
cp -r ../setup.py .
