#
# RPM Spec for pScheduler BWCTL iperf2 Tool
#

%define short	bwctliperf2
Name:		pscheduler-tool-%{short}
Version:	1.1.1
Release:	1%{?dist}

Summary:	bwctliperf2 tool class for pScheduler
BuildArch:	noarch
License:	ASL 2.0
Vendor:	perfSONAR
Group:		Unspecified

Source0:	%{short}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	pscheduler-server
Requires:	python-pscheduler >= 1.3
Requires:	pscheduler-test-throughput
Requires:	bwctl-client
Requires:	bwctl-server
requires:	iperf

BuildRequires:	pscheduler-rpm


%description
bwctliperf2 tool class for pScheduler


%prep
%if 0%{?el6}%{?el7} == 0
echo "This package cannot be built on %{dist}."
false
%endif

%setup -q -n %{short}-%{version}


%define dest %{_pscheduler_tool_libexec}/%{short}

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
%license LICENSE
%{dest}
