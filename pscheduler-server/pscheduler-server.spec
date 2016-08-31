#
# RPM Spec for pScheduler Server
#

# TODO: Need to write proper systemd services for this package and
# make the scriptlets use them on CentOS 7.  For now the old-style
# init scripts function just fine.

Name:		pscheduler-server
Version:	0.0
Release:	1%{?dist}

Summary:	pScheduler Server
BuildArch:	noarch
License:	Apache 2.0
Group:		Unspecified

Source0:	%{name}-%{version}.tar.gz

Provides:	%{name} = %{version}-%{release}

Requires:	curl
Requires:	pscheduler-account
Requires:	pscheduler-database
Requires:	python-daemon
Requires:	python-Flask
Requires:	python-ipaddr
Requires:	python-requests
Requires:	python-jsontemplate

BuildRequires:	m4

%description
The pScheduler server

%define log_dir %{_var}/log/pscheduler
%define archiver_default_dir %{_pscheduler_sysconfdir}/default-archives


%prep
%if 0%{?el6}%{?el7} == 0
echo "This package cannot be built for %{dist}."
false
%endif
%setup -q


%build
make \
     DAEMONDIR=%{_pscheduler_daemons} \
     DSNFILE=%{_pscheduler_database_dsn_file} \
     LOGDIR=%{log_dir} \
     PGDATABASE=%{_pscheduler_database_name} \
     PGPASSFILE=%{_pscheduler_database_pgpass_file} \
     PGUSER=%{_pscheduler_database_user} \
     PSUSER=%{_pscheduler_user} \
     ARCHIVERDEFAULTDIR=%{archiver_default_dir} \
     VAR=%{_var}


%install
make \
     INITDDIR=$RPM_BUILD_ROOT/%{_initddir} \
     DAEMONDIR=$RPM_BUILD_ROOT/%{_pscheduler_daemons} \
     COMMANDDIR=$RPM_BUILD_ROOT/%{_pscheduler_commands} \
     install

mkdir -p $RPM_BUILD_ROOT/%{archiver_default_dir}
mkdir -p $RPM_BUILD_ROOT/%{log_dir}


%pre
if [ "$1" -eq 2 ]
then
    for SERVICE in ticker runner archiver scheduler
    do
        NAME="pscheduler-${SERVICE}"
        service "${NAME}" stop
        chkconfig "${NAME}" off
    done
fi


%post
for SERVICE in ticker runner archiver scheduler
do
    NAME="pscheduler-${SERVICE}"
    chkconfig "${NAME}" on
    service "${NAME}" start
done


%preun
for SERVICE in ticker runner archiver scheduler
do
    NAME="pscheduler-${SERVICE}"
    service "${NAME}" stop
    chkconfig "${NAME}" off
done


%files
%defattr(-,root,root,-)
%{_initddir}/*
%{_pscheduler_daemons}/*
%{_pscheduler_commands}/*
%attr(750,%{_pscheduler_user},%{_pscheduler_group}) %{archiver_default_dir}
%attr(750,%{_pscheduler_user},%{_pscheduler_group}) %{log_dir}
