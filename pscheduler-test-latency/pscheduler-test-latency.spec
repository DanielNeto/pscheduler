#
# RPM Spec for pScheduler Latency Test
#

%define short	latency
Name:		pscheduler-test-%{short}
Version:	0.0
Release:	1%{?dist}

Summary:	Latency test class for pScheduler
BuildArch:	noarch
License:	Apache 2.0
Group:		Unspecified

Source0:	%{short}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	pscheduler-core
Requires:	python-pscheduler
Requires:   python-jsonschema

BuildRequires:	pscheduler-rpm


%description
Latency test class for pScheduler


%prep
%setup -q -n %{short}-%{version}


%define dest %{_pscheduler_test_libexec}/%{short}

%build
make \
     DESTDIR=$RPM_BUILD_ROOT/%{dest} \
     DOCDIR=$RPM_BUILD_ROOT/%{_pscheduler_test_doc} \
     CONFDIR=$RPM_BUILD_ROOT/%{_pscheduler_testconfdir}\
     install


%files
%defattr(-,root,root,-)
%config(noreplace) %{_pscheduler_testconfdir}/*
%{dest}
%{_pscheduler_test_doc}/*
