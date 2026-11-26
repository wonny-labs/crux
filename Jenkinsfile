// Crux CI on Jenkins: a thin wrapper around scripts/ci/run-tier.sh (docs/ci.md#jenkins).
//
// A Multibranch Pipeline builds branches and change requests. The tier comes from the build:
// a branch build runs fast, a change request full, the default branch full after a merge, and the
// nightly timer on the default branch runs nightly. The TIER parameter overrides it.
// Every stage builds the Dev Container image without the J-Link software (CRUX_JLINK=0) and runs
// one job of scripts/ci/checks.toml through scripts/ci/jenkins/run-job.sh. The web stages need
// an agent labelled crux-web with Node.js and Google Chrome.

// Runs one job, publishes its JUnit report and logs, then removes the stage's workspace,
// which also holds the west workspace of the build.
def runJob(String job) {
    try {
        sh "scripts/ci/jenkins/run-job.sh ${job}"
    } finally {
        junit allowEmptyResults: true, testResults: 'build/ci/*.junit.xml'
        archiveArtifacts allowEmptyArchive: true, artifacts: 'build/ci/**'
        dir('..') {
            deleteDir()
        }
    }
}

pipeline {
    agent none
    parameters {
        choice(name: 'TIER', choices: ['auto', 'fast', 'full', 'nightly'],
               description: 'CI tier (docs/ci.md). auto decides from the build.')
    }
    triggers {
        cron(env.BRANCH_NAME == 'main' ? 'H 2 * * *' : '')
    }
    options {
        disableConcurrentBuilds(abortPrevious: env.BRANCH_NAME != 'main')
        timeout(time: 3, unit: 'HOURS')
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }
    environment {
        TIER = "${params.TIER ?: 'auto'}"
        CRUX_CI_TRIGGER = "${currentBuild.getBuildCauses('hudson.triggers.TimerTrigger$TimerTriggerCause') ? 'timer' : ''}"
        CRUX_CACHE_DIR = '/opt/crux-cache'
        ZEPHYR_SDK_INSTALL_DIR = '/opt/crux-cache/sdk/zephyr-sdk-1.0.1'
        CLANG_FORMAT = 'clang-format'
        CC = 'clang-18'
        CXX = 'clang++-18'
    }
    stages {
        stage('Checks') {
            parallel {
                stage('host') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/host/crux-pilot" } }
                    steps { script { runJob('host') } }
                }
                stage('host-build-tests') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/host-build-tests/crux-pilot" } }
                    steps { script { runJob('host-build-tests') } }
                }
                stage('zephyr-storage') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/zephyr-storage/crux-pilot" } }
                    steps { script { runJob('zephyr-storage') } }
                }
                stage('zephyr-controller') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/zephyr-controller/crux-pilot" } }
                    steps { script { runJob('zephyr-controller') } }
                }
                stage('zephyr-runtime') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/zephyr-runtime/crux-pilot" } }
                    steps { script { runJob('zephyr-runtime') } }
                }
                stage('zephyr-io') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/zephyr-io/crux-pilot" } }
                    steps { script { runJob('zephyr-io') } }
                }
                stage('psa-crypto') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/psa-crypto/crux-pilot" } }
                    steps { script { runJob('psa-crypto') } }
                }
                stage('docs') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/docs/crux-pilot" } }
                    steps { script { runJob('docs') } }
                }
                stage('coverage-host') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/coverage-host/crux-pilot" } }
                    steps { script { runJob('coverage-host') } }
                }
                stage('coverage-native-sim') {
                    agent { dockerfile { filename '.devcontainer/Dockerfile'; dir '.'; additionalBuildArgs '--build-arg CRUX_JLINK=0'; args '-v crux-ci-cache:/opt/crux-cache'; customWorkspace "crux-ci/${env.BUILD_TAG}/coverage-native-sim/crux-pilot" } }
                    steps { script { runJob('coverage-native-sim') } }
                }
                stage('web-specification') {
                    agent { node { label 'crux-web'; customWorkspace "crux-ci/${env.BUILD_TAG}/web-specification/crux-pilot" } }
                    steps { script { runJob('web-specification') } }
                }
                stage('web-client') {
                    agent { node { label 'crux-web'; customWorkspace "crux-ci/${env.BUILD_TAG}/web-client/crux-pilot" } }
                    steps { script { runJob('web-client') } }
                }
                stage('web-browser') {
                    agent { node { label 'crux-web'; customWorkspace "crux-ci/${env.BUILD_TAG}/web-browser/crux-pilot" } }
                    steps { script { runJob('web-browser') } }
                }
                stage('web-angular') {
                    agent { node { label 'crux-web'; customWorkspace "crux-ci/${env.BUILD_TAG}/web-angular/crux-pilot" } }
                    steps { script { runJob('web-angular') } }
                }
            }
        }
    }
}
