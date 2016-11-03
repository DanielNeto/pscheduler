#
# RPM Spec for pScheduler BWCTL Traceroute Tool
#

%define short	bwctltraceroute
Name:		pscheduler-tool-%{short}
Version:	1.0
Release:	0.15.rc2%{?dist}

Summary:	pScheduler BWCTL Traceroute Tool
BuildArch:	noarch
License:	Apache 2.0
Group:		Unspecified

Source0:	%{short}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	pscheduler-server
Requires:	pscheduler-account
Requires:	python-pscheduler
Requires:	pscheduler-test-trace
Requires:	python-icmperror
Requires:	bwctl-client
Requires:	bwctl-server
Requires:   traceroute

BuildRequires:	pscheduler-account
BuildRequires:	pscheduler-rpm

%description
pScheduler BWCTL Traceroute Tool


%prep
%setup -q -n %{short}-%{version}


%define dest %{_pscheduler_tool_libexec}/%{short}

%install
make \
     DESTDIR=$RPM_BUILD_ROOT/%{dest} \
     DOCDIR=$RPM_BUILD_ROOT/%{_pscheduler_tool_doc} \
     install



%post
pscheduler internal warmboot


%postun
pscheduler internal warmboot


%files
%defattr(-,root,root,-)
%{dest}
