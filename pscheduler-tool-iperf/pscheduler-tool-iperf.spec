#
# RPM Spec for pScheduler iperf Tool
#

%define short	iperf
Name:		pscheduler-tool-%{short}
Version:	0.0
Release:	1%{?dist}

Summary:	iperf tool class for pScheduler
BuildArch:	noarch
License:	Apache 2.0
Group:		Unspecified

Source0:	%{short}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	pscheduler-core
Requires:	python-pscheduler
Requires:	pscheduler-test-throughput
requires:	iperf

BuildRequires:	pscheduler-rpm


%define directory %{_includedir}/make

%description
iperf tool class for pScheduler


%prep
%setup -q -n %{short}-%{version}


%define dest %{_pscheduler_tool_libexec}/%{short}

%build
make \
     DESTDIR=$RPM_BUILD_ROOT/%{dest} \
     DOCDIR=$RPM_BUILD_ROOT/%{_pscheduler_tool_doc} \
     install

%post
if [ "$1" -eq 1 ]
then
    # Put our rule after the last ACCEPT in the input chain
    INPUT_LENGTH=$(iptables -L INPUT | egrep -e '^ACCEPT' | wc -l)
    iptables -I INPUT $(expr ${INPUT_LENGTH} + 1 ) \
        -p tcp -m state --state NEW -m tcp --dport 5001:5300 -j ACCEPT
    service iptables save
fi

%postun
if [ "$1" -eq 0 ]
then
    iptables -D INPUT \
        -p tcp -m state --state NEW -m tcp --dport 5001:5300 -j ACCEPT
    service iptables save
fi


%files
%defattr(-,root,root,-)
%{dest}
%{_pscheduler_tool_doc}/*
