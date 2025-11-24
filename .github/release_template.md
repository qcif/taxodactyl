# {{ version }}

## If this is a Python scripts release:

- [ ] The release should be tagged like `x.x.x-dev`
- [ ] Set this as a pre-release
- [ ] Replace the `{{ version }}` placeholders in this template
- [ ] Ensure that [./scripts/VERSION](https://github.com/qcif/taxodactyl/blob/main/scripts/VERSION) file has been updated
- [ ] Ensure that [./scripts/pyproject.toml](https://github.com/qcif/taxodactyl/blob/main/scripts/VERSION) file has been updated
- [ ] Click on "Generate release notes" to get a detailed changelog (if major updates are PRs, this is likely enough)
- [ ] Filter issues/pull-requests to `milestone:release_x.x.x` to see high-level changes since last version
- [ ] Use the above to fill out the sections below
- [ ] Ensure that any feature updates have been documented
- [ ] Delete this checklist


## If this is a workflow (Nextflow) release:

- [ ] The release should be tagged like `x.x.x` (identical version to Python release)
- [ ] Replace the `{{ version }}` placeholders in this template
- [ ] Copy the release notes from the Python release
- [ ] Ensure that version is updated in `conf/manifest.config`
- [ ] Ensure that any feature updates have been documented
- [ ] Delete this checklist

---

### Summary

Provide a brief overview of the content of this release

### Major changes

(list major features implemented)

### Minor changes

(list commits/PRs)

### Bug fixes

(list bug fix commits/PRs)

---

Pull the docker image: [neoformit/taxodactyl:v{{ version }}](https://hub.docker.com/r/neoformit/taxodactyl/tags)
