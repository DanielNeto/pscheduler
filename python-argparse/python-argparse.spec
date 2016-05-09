#
# RPM Spec for Python Argparse
#

# TODO: This is required for 2.6 but became part of Python in 2.7

%define short	argparse
Name:		python-%{short}
Version:	1.4.0
Release:	1%{?dist}
Summary:	Python argument parser
BuildArch:	noarch
License:	Python Software Foundation License
Group:		Development/Libraries

Provides:	%{name} = %{version}-%{release}
Prefix:		%{_prefix}

Vendor:		Thomas Waldmann
URL:		https://github.com/ThomasWaldmann/argparse

Source:		%{short}-%{version}.tar.gz

Requires:	python

BuildRequires:	python
BuildRequires:	python-setuptools

%description
Python argument parser



# Don't do automagic post-build things.
%global              __os_install_post %{nil}


%prep
%setup -q -n %{short}-%{version}


%build
python setup.py build


%install
python setup.py install --root=$RPM_BUILD_ROOT --single-version-externally-managed -O1  --record=INSTALLED_FILES


%clean
rm -rf $RPM_BUILD_ROOT


%files -f INSTALLED_FILES
%defattr(-,root,root)
