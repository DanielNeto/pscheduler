#
# RPM Spec for pScheduler Latency Test
#

%define short	latency
Name:		pscheduler-test-%{short}
Version:	1.0.0.3.1
Release:	1%{?dist}

Summary:	Latency test class for pScheduler
BuildArch:	noarch
License:	Apache 2.0
Group:		Unspecified

Source0:	%{short}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	pscheduler-server >= 1.0.0.3.1
Requires:	python-pscheduler
Requires:	python-jsontemplate

BuildRequires:	pscheduler-rpm


%description
Latency test class for pScheduler


%prep
%setup -q -n %{short}-%{version}


%define dest %{_pscheduler_test_libexec}/%{short}

%build
make \
     DESTDIR=$RPM_BUILD_ROOT/%{dest} \
     install



%post
pscheduler internal warmboot


%postun
pscheduler internal warmboot


%files
%defattr(-,root,root,-)
%{dest}
