#!/usr/bin/env groovy
pipeline {
  /**
  agent {
    docker {
      image 'fedora:28'
      args '-e en_US.UTF-8 --privileged -u root:root --hostname master.ipa.test'
      reuseNode true
    }
  } **/
  agent { label 'openstack' }
  options {
    buildDiscarder(logRotator(numToKeepStr:'5'))
    timeout(time: 90, unit: 'MINUTES')
  }
  stages {
    stage('Pipeline validation') {
      steps {
        validateDeclarativePipeline 'Jenkinsfile'
      }
    }
    stage('Build environment preparation') {
      steps {
        sh 'sudo dnf update -y'
        sh 'sudo dnf builddep -y -b -D "with_python3 1" -D "with_wheels 1" -D "with_lint 1" --spec freeipa.spec.in --best --allowerasing'
      }
    }
    stage('Configure') {
      steps {
        sh 'autoreconf -i'
        sh './configure'
      }
    }
    stage('Tox') {
      steps {
        parallel(
          pylint3: {
            sh 'cp -va ${WORKSPACE} /tmp/tox_pylint3'
            dir('/tmp/tox_pylint3'){
                sh 'tox -e pylint3'
                deleteDir()
            }
          },
          py36: {
            sh 'cp -va ${WORKSPACE} /tmp/tox_py36'
            dir('/tmp/tox_py36'){
                sh 'tox -e py36'
                deleteDir()
            }
          },
          pypi: {
            sh 'cp -va ${WORKSPACE} /tmp/tox_pypi'
            dir('/tmp/tox_pypi'){
              sh 'tox -e pypi'
              deleteDir()
            }
          }
        )
      }
    }
    stage('WebUI Unit tests') {
      steps {
        sh 'sudo dnf install -y npm'
        sh 'cd ${WORKSPACE}/install/ui/js/libs && make'
        sh 'cd ${WORKSPACE}/install/ui && npm install'
        sh 'cd ${WORKSPACE}/install/ui && node_modules/grunt/bin/grunt --verbose test'
      }
      post {
        always {
          junit 'install/ui/_build/test-reports/TEST-all_tests.xml'
        }
      }
    }
    stage('Build') {
      steps {
        sh './makerpms.sh'
      }
    }
    // TODO: Stash for later stages
    stage('Create repo') {
      steps {
        sh 'createrepo --database ${WORKSPACE}/rpmbuild/RPMS/'
	sh '''
cat <<EOF >"${WORKSPACE}/rpmbuild/RPMS/local.repo"
[local]
name=Freeipa Build for
baseurl=file://${WORKSPACE}/rpmbuild/RPMS/
gpgcheck=0
enabled=1
EOF
        '''
        stash name: 'repo', includes: 'rpmbuild/RPMS/**'
      }
    }
    stage('Test') {
        agent { label 'openstack' }
        environment {
          PATH = '/usr/sbin:/usr/bin:/bin:/usr/local/bin:/usr/local/sbin'
          LANG = 'en_US.UTF-8'
        }  
        steps {
              unstash name: 'repo'
              sh 'sudo hostnamectl set-hostname master.ipa.test'
              sh 'ls -lah ${WORKSPACE}/rpmbuild/RPMS/'
              sh 'sudo cp -v ${WORKSPACE}/rpmbuild/RPMS/local.repo /etc/yum.repos.d/'
              sh 'sudo dnf update -y'
              sh 'sudo dnf install -y freeipa-server freeipa-server-dns freeipa-server-trust-ad freeipa-client python3-ipatests'
              sh 'sudo ipa-server-install -U --domain ipa.test --realm ipa.test -p Secret123 -a Secret123 --setup-dns --setup-kra --auto-forwarders'
              sh 'echo Secret123 | kinit admin && ipa ping'
              sh 'sudo cp -r /etc/ipa/* ~/.ipa/'
              sh 'echo Secret123 > ~/.ipa/.dmpw'
              sh 'sudo chown -R fedora ~/.ipa'
              sh 'echo "wait_for_dns=5" >> ~/.ipa/default.conf'
              sh 'which ipa-getkeytab'
              sh 'ipa-run-tests-3 -v --junit-xml=junit.xml test_cmdline test_install test_ipaclient test_ipalib test_ipaplatform test_ipapython test_ipaserver test_xmlrpc'
        }
          post {
              always {
                  junit 'junit.xml'
              }
          }
        }
      }
      post {
          always {
              cleanWs(cleanWhenAborted: true, cleanWhenFailure: true, cleanWhenNotBuilt: true, cleanWhenSuccess: true, cleanWhenUnstable: true, cleanupMatrixParent: true, deleteDirs: true)
          }
    }
}
