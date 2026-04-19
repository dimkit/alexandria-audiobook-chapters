const HOST_PYTHON = "{{which('python') || 'python'}}"
const PYTEST_EXTRA_ARGS = "{{args.pytest ? '--pytest-args \"' + args.pytest + '\"' : ''}}"
const FRESH_CLONE_FLAG = "{{args.run_fresh_clone_e2e ? '--fresh-clone-e2e' : ''}}"
const SPLIT_STAGE_FLAG = "{{args.split_stage_ui ? '--split-stage-ui' : ''}}"
const SANITY_STRICT_FLAG = "{{args.sanity_strict ? '--sanity-strict' : ''}}"
const SKIP_SANITY_FLAG = "{{args.skip_sanity ? '--skip-sanity' : ''}}"

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: ".",
        message: `${HOST_PYTHON} run_tests.py ${PYTEST_EXTRA_ARGS} ${FRESH_CLONE_FLAG} ${SPLIT_STAGE_FLAG} ${SANITY_STRICT_FLAG} ${SKIP_SANITY_FLAG}`
      }
    }
  ]
}
