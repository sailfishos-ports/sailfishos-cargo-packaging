# Only x86_64 and i686 are Tier 1 platforms at this time.
# https://forge.rust-lang.org/platform-support.html
%global rust_arches x86_64 i686 armv7hl aarch64 ppc64 ppc64le s390x

# Only the specified arches will use bootstrap binaries.
#global bootstrap_arches %%{rust_arches}

%if 0%{?rhel} && !0%{?epel}
%bcond_without bundled_libgit2
%else
%bcond_with bundled_libgit2
%endif

Name:           cargo
Version:        0.22.0
Release:        1%{?dist}
Summary:        Rust's package manager and build tool
License:        ASL 2.0 or MIT
URL:            https://crates.io/
ExclusiveArch:  %{rust_arches}

%global cargo_version %{version}
%global cargo_bootstrap 0.21.0

Source0:        https://github.com/rust-lang/%{name}/archive/%{cargo_version}/%{name}-%{cargo_version}.tar.gz

# Get the Rust triple for any arch.
%{lua: function rust_triple(arch)
  local abi = "gnu"
  if arch == "armv7hl" then
    arch = "armv7"
    abi = "gnueabihf"
  elseif arch == "ppc64" then
    arch = "powerpc64"
  elseif arch == "ppc64le" then
    arch = "powerpc64le"
  end
  return arch.."-unknown-linux-"..abi
end}

%global rust_triple %{lua: print(rust_triple(rpm.expand("%{_target_cpu}")))}

%if %defined bootstrap_arches
# For each bootstrap arch, add an additional binary Source.
# Also define bootstrap_source just for the current target.
%{lua: do
  local bootstrap_arches = {}
  for arch in string.gmatch(rpm.expand("%{bootstrap_arches}"), "%S+") do
    table.insert(bootstrap_arches, arch)
  end
  local base = rpm.expand("https://static.rust-lang.org/dist/cargo-%{cargo_bootstrap}")
  local target_arch = rpm.expand("%{_target_cpu}")
  for i, arch in ipairs(bootstrap_arches) do
    i = i + 10
    print(string.format("Source%d: %s-%s.tar.xz\n",
                        i, base, rust_triple(arch)))
    if arch == target_arch then
      rpm.define("bootstrap_source "..i)
    end
  end
end}
%endif

# Use vendored crate dependencies so we can build offline.
# Created using https://github.com/alexcrichton/cargo-vendor/ 0.1.12
# It's so big because some of the -sys crates include the C library source they
# want to link to.  With our -devel buildreqs in place, they'll be used instead.
# FIXME: These should all eventually be packaged on their own!
Source100:      %{name}-%{version}-vendor.tar.xz

BuildRequires:  rust
BuildRequires:  make
BuildRequires:  cmake
BuildRequires:  gcc

%ifarch %{bootstrap_arches}
%global bootstrap_root cargo-%{cargo_bootstrap}-%{rust_triple}
%global local_cargo %{_builddir}/%{bootstrap_root}/cargo/bin/cargo
Provides:       bundled(%{name}-bootstrap) = %{cargo_bootstrap}
%else
BuildRequires:  %{name} >= 0.13.0
%global local_cargo %{_bindir}/%{name}
%endif

# Indirect dependencies for vendored -sys crates above
BuildRequires:  libcurl-devel
BuildRequires:  libssh2-devel
BuildRequires:  openssl-devel
BuildRequires:  zlib-devel
BuildRequires:  pkgconfig

%if %with bundled_libgit2
Provides:       bundled(libgit2) = 0.25.0
%else
BuildRequires:  libgit2-devel >= 0.24
%endif

# Cargo is not much use without Rust
Requires:       rust

%description
Cargo is a tool that allows Rust projects to declare their various dependencies
and ensure that you'll always get a repeatable build.


%package doc
Summary:        Documentation for Cargo
BuildArch:      noarch

%description doc
This package includes HTML documentation for Cargo.


%prep

%ifarch %{bootstrap_arches}
%setup -q -n %{bootstrap_root} -T -b %{bootstrap_source}
test -f '%{local_cargo}'
%endif

# cargo sources
%setup -q -n %{name}-%{cargo_version}

# vendored crates
%setup -q -n %{name}-%{cargo_version} -T -D -a 100

# define the offline registry
%global cargo_home $PWD/.cargo
mkdir -p %{cargo_home}
cat >.cargo/config <<EOF
[source.crates-io]
registry = 'https://github.com/rust-lang/crates.io-index'
replace-with = 'vendored-sources'

[source.vendored-sources]
directory = '$PWD/vendor'
EOF

# This should eventually migrate to distro policy
# Enable optimization, debuginfo, and link hardening.
%global rustflags -Copt-level=3 -Cdebuginfo=2 -Clink-arg=-Wl,-z,relro,-z,now

%build

%if %without bundled_libgit2
# convince libgit2-sys to use the distro libgit2
export LIBGIT2_SYS_USE_PKG_CONFIG=1
%endif

# use our offline registry and custom rustc flags
export CARGO_HOME="%{cargo_home}"
export RUSTFLAGS="%{rustflags}"

# cargo no longer uses a configure script, but we still want to use
# CFLAGS in case of the odd C file in vendored dependencies.
%{?__global_cflags:export CFLAGS="%{__global_cflags}"}
%{!?__global_cflags:%{?optflags:export CFLAGS="%{optflags}"}}
%{?__global_ldflags:export LDFLAGS="%{__global_ldflags}"}

%{local_cargo} build --release
sh src/ci/dox.sh


%install
export CARGO_HOME="%{cargo_home}"
export RUSTFLAGS="%{rustflags}"

%{local_cargo} install --root %{buildroot}%{_prefix}
rm %{buildroot}%{_prefix}/.crates.toml

mkdir -p %{buildroot}%{_mandir}/man1
%{__install} -p -m644 src/etc/man/cargo*.1 \
  -t %{buildroot}%{_mandir}/man1

%{__install} -p -m644 src/etc/cargo.bashcomp.sh \
  -D %{buildroot}%{_sysconfdir}/bash_completion.d/cargo

%{__install} -p -m644 src/etc/_cargo \
  -D %{buildroot}%{_datadir}/zsh/site-functions/_cargo

# Create the path for crate-devel packages
mkdir -p %{buildroot}%{_datadir}/cargo/registry

mkdir -p %{buildroot}%{_docdir}/cargo
cp -a target/doc %{buildroot}%{_docdir}/cargo/html


%check
export CARGO_HOME="%{cargo_home}"
export RUSTFLAGS="%{rustflags}"

# some tests are known to fail exact output due to libgit2 differences
CFG_DISABLE_CROSS_TESTS=1 %{local_cargo} test --no-fail-fast || :


%files
%license LICENSE-APACHE LICENSE-MIT LICENSE-THIRD-PARTY
%doc README.md
%{_bindir}/cargo
%{_mandir}/man1/cargo*.1*
%{_sysconfdir}/bash_completion.d/cargo
%{_datadir}/zsh/site-functions/_cargo
%dir %{_datadir}/cargo
%dir %{_datadir}/cargo/registry

%files doc
%{_docdir}/cargo/html


%changelog
* Mon Oct 16 2017 Josh Stone <jistone@redhat.com> - 0.22.0-1
- Update to 0.22.0

* Mon Sep 11 2017 Josh Stone <jistone@redhat.com> - 0.21.1-1
- Update to 0.21.1.

* Thu Aug 31 2017 Josh Stone <jistone@redhat.com> - 0.21.0-1
- Update to 0.21.0.

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.20.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.20.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Jul 21 2017 Josh Stone <jistone@redhat.com> - 0.20.0-1
- Update to 0.20.0.
- Add a cargo-doc subpackage.

* Sat Jul 08 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.19.0-4
- Disable bootstrap

* Sat Jul 08 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.19.0-3
- Rebuild for libgit2 0.26.x

* Tue Jun 20 2017 Josh Stone <jistone@redhat.com> - 0.19.0-2
- Create /usr/share/cargo/registry for crate-devel packages

* Fri Jun 09 2017 Josh Stone <jistone@redhat.com> - 0.19.0-1
- Update to 0.19.0.

* Thu Apr 27 2017 Josh Stone <jistone@redhat.com> - 0.18.0-1
- Update to 0.18.0.

* Thu Mar 16 2017 Josh Stone <jistone@redhat.com> - 0.17.0-1
- Update to 0.17.0.

* Tue Feb 14 2017 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 0.16.0-2
- Backport patch to expose description in cargo metadata

* Thu Feb 09 2017 Josh Stone <jistone@redhat.com> - 0.16.0-1
- Update to 0.16.0.
- Start using the current upstream release for bootstrap.
- Merge and clean up conditionals for epel7.

* Tue Feb 07 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.15.0-4
- Disable bootstrap

* Tue Feb 07 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.15.0-3
- Rebuild for libgit2-0.25.x

* Tue Jan 03 2017 Josh Stone <jistone@redhat.com> - 0.15.0-2
- Rebuild without bootstrap binaries.

* Tue Jan 03 2017 Josh Stone <jistone@redhat.com> - 0.15.0-1
- Update to 0.15.0.
- Rewrite bootstrap logic to target specific arches.
- Bootstrap ppc64, ppc64le, s390x.

* Sun Nov 13 2016 Josh Stone <jistone@redhat.com> - 0.14.0-2
- Fix CFG_RELEASE_NUM

* Thu Nov 10 2016 Josh Stone <jistone@redhat.com> - 0.14.0-1
- Update to 0.14.0.
- Use hardening flags for linking.

* Thu Oct 20 2016 Josh Stone <jistone@redhat.com> - 0.13.0-4
- Rebuild with Rust 1.12.1 and enabled MIR.

* Fri Oct 07 2016 Josh Stone <jistone@redhat.com> - 0.13.0-3
- Rebuild without bootstrap binaries.

* Thu Oct 06 2016 Josh Stone <jistone@redhat.com> - 0.13.0-2
- Bootstrap aarch64.
- Use jemalloc's MALLOC_CONF to work around #36944.

* Fri Sep 30 2016 Josh Stone <jistone@redhat.com> - 0.13.0-1
- Update to 0.13.0.
- Always use --local-cargo, even for bootstrap binaries.
- Disable MIR until rust#36774 is resolved.

* Sat Sep 03 2016 Josh Stone <jistone@redhat.com> - 0.12.0-3
- Rebuild without bootstrap binaries.

* Fri Sep 02 2016 Josh Stone <jistone@redhat.com> - 0.12.0-2
- Bootstrap armv7hl.
- Patch dl-snapshot.py to ignore hashes on unknown archs.

* Wed Aug 24 2016 Josh Stone <jistone@redhat.com> - 0.12.0-1
- Update to 0.12.0.

* Mon Aug 22 2016 Josh Stone <jistone@redhat.com> 0.11.0-3
- Rebuild without bootstrap binaries.
- Add a runtime requirement on rust.

* Mon Aug 22 2016 Josh Stone <jistone@redhat.com> - 0.11.0-2
- Initial import into Fedora (#1357749), bootstrapped

* Sun Jul 17 2016 Josh Stone <jistone@fedoraproject.org> - 0.11.0-1
- Initial package, bootstrapped
