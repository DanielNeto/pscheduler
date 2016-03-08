#
# RPM Spec for pScheduler Syslog Archiver
#

%define short	syslog
Name:		pscheduler-archiver-%{short}
Version:	0.0
Release:	1%{?dist}

Summary:	Bitbucket archiver class for pScheduler
BuildArch:	noarch
License:	Apache 2.0
Group:		Unspecified

Source0:	%{short}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	pscheduler-core

BuildRequires:	pscheduler-rpm


%define directory %{_includedir}/make

%description
This archiver disposes of measurements by dropping them on the floor.


%prep
%setup -q -n %{short}-%{version}


%define dest %{_pscheduler_archiver_libexec}/%{short}

%build
make \
     DESTDIR=$RPM_BUILD_ROOT/%{dest} \
     DOCDIR=$RPM_BUILD_ROOT/%{_pscheduler_archiver_doc} \
     install


%files
%defattr(-,root,root,-)
%{dest}
%{_pscheduler_archiver_doc}/*
