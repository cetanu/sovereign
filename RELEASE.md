Release Process
===============

Making changes
--------------
Contributors should create a new branch from the `master` branch for any new
features or bug fixes

Once the changes are complete:

* Write a good commit message, including a body
* Add your changes to [CHANGELOG.md]
* Increment the appropriate version in [pyproject.toml]
* Open a pull-request, have it reviewed
* Merge the branch back into `master`


Releasing a new major/minor version
-----------------------------------
When it is time to release the version, checkout `master` and create a new
branch named `release/<version>` without the patch number. For example, `release/0.29`

Do not merge the branch back into `master`


Upload to PyPI
--------------
⚠️ Warning: once a release has been uploaded to PyPI it cannot be deleted
without manual action by the package maintainer

Create & push a tag on the last commit in the `release/<version>` branch


Patch process
-------------
Follow the above process, but check out the specific `release/<version>` branch
that requires the patch, instead of `master`

You will still need to create a new branch from this release branch for the
patch, and open a pull-request to merge onto the `release/<version>` branch
that you checked out

If a security patch is required, apply the same patch to the last 5 minor
versions by checking out each release branch


Release cadence / schedule
--------------------------
To be determined, no schedule as yet. Realistically, after there is a
significant batch of changes that have been tested in our internal environment
for some time and seem stable

If development picks up and many changes are backed up, we will set a regular
release cadence


Example workflows
----------------
### Major/minor release
1. Make sure you're working off the latest
    ```shell
    git checkout master
    git pull
    ```
2. Create a new branch in the format `<username>/<summary>`
    ```
    git checkout -b bobsmith/my_changes
    ```
3. Add changes to the branch
4. Open a pull-request and merge the branch onto `master`
5. Create a release branch and push it to the repo
    ```
    git checkout -b release/1.2
    git push -u origin release/1.2
    ```
6. Trigger the upload to PyPI
    ```
    git tag 1.2
    git push --tags
    ```

### Patch release
1. Create a patch branch
    ```
    git checkout release/1.2
    git checkout -b patch/1.2.3
    ```
2. Add changes to the branch
3. Open a pull-request and merge the `patch/1.2.3` onto `release/1.2`
4. Trigger the upload to PyPI
    ```
    git tag 1.2.3
    git push --tags
    ```


Important Notes
---------------
- **Versioning**: Follow [semver](https://semver.org) for naming your release and patch versions
- **Documentation**: Update any relevant documentation in [sovereign-docs](https://bitbucket.org/atlassian/sovereign-docs)
