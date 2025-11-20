# {{ version }}

>[!NOTE] First make a x.x.x-dev release to trigger Python container build, then
> make x.x.x release when Nextflow has been tested with new Python container

- [ ] Ensure that [scripts/VERSION](https://github.com/qcif/taxodactyl/blob/main/scripts/VERSION) file has been updated
- [ ] Filter issues/pull-requests to `milestone:release_x.x.x` to see high-level changes since last version
- [ ] Click on "Generate release notes" to get a detailed changelog
- [ ] Use the above to fill out the sections below

### Summary

- Provide a brief overview of the content of this release

### Major changes


### Minor changes

(list commits/PRs)


### Bug fixes

(list bug fix commits/PRs)

---

Pull the docker image: neoformit/taxodactyl:v{{ version }}
