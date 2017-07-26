#
# RPM Spec for Python JQ Bindings
#

%define short	jq
Name:		python-%{short}
Version:	0.1.6
Release:	1%{?dist}
Summary:	Python bindings for jq
BuildArch:	%(uname -m)
License:	BSD
Group:		Development/Libraries

Provides:	%{name} = %{version}-%{release}
Prefix:		%{_prefix}

Vendor:		Michael Williamson
URL:		https://github.com/mwilliamson/jq.py

Source:		%{short}-%{version}.tar.gz

Patch0:		%{name}-%{version}-00-nodownloads.patch

Requires:	python
Requires:	jq >= 1.5
Requires:	oniguruma >= 5.9

BuildRequires:	python
BuildRequires:	python-setuptools
BuildRequires:	Cython >= 0.19
BuildRequires:	jq-devel >= 1.5
BuildRequires:	oniguruma-devel >= 5.9

%description
Python bindings for JQ



# Don't do automagic post-build things.
%global              __os_install_post %{nil}


%prep
%setup -q -n %{short}-%{version}
%patch0 -p1


%build
#python setup.py build
python setup.py build_ext --inplace


%install
python setup.py install --root=$RPM_BUILD_ROOT -O1  --record=INSTALLED_FILES


%clean
rm -rf $RPM_BUILD_ROOT


%files -f INSTALLED_FILES
%defattr(-,root,root)
