import lib
from glob import glob


class GarbageCollector(object):
    """
    Matches index with registry and cleans up mismatched data from the registry.
    """

    def __init__(self, registry_host="127.0.0.1", registry_port="5000", registry_secure=False, local_index=False,
                 index_git="https://github.com/centos/container-index"):
        """
        Initialize the garbage collector object.

        :param registry_host: The ip or host name of registry to query. Default is 127.0.0.1.
        :param registry_port: The port of the registry to query. Default is 5000
        :param registry_secure: Is the registry secure or insecure (https or http)
        :param local_index: Is the index to query locally available.
        :param index_git: If the index is on a git repo, the url of that repo.
        """
        self._index_location = "./c_i"
        if local_index:
            # If local index is set, check if inex files are present at expected location.
            if not lib.path.exists(self._index_location):
                raise Exception("Local index specified, but does not exist")
        else:
            # Otherwise clone index.
            print("Cloning container index...")
            lib.clone_repo(self._index_git, self._index_location)
        self._index_git = index_git
        # Formulate the registry url
        self._registry_url = str.format("{schema}://{host}{port}/v2",
                                        schema="https" if registry_secure else "http",
                                        host=registry_host,
                                        port="" if not registry_port else ":" + registry_port
                                        )
        self._index_location = self._index_location + "/index.d"
        # Setup reg info object to query the registry and cache metadata.
        self._registry_info = lib.RegistryInfo(self._registry_url)
        self.index_containers = {}
        self.mismatched = {}

    def _delete_mismatched(self):
        """Deletes the mismatched images from registry."""
        registry_storage_path = "/var/lib/registry/docker/registry/v2"
        registry_blobs = registry_storage_path + "/blobs"
        registry_repositories = registry_storage_path + "/repositories"
        for k, v in self.mismatched.iteritems():
            # For every entry in mismatched
            ## Formulate nessasary data
            namespace = k.split("/")[0]
            namespace_path = registry_repositories + "/" + namespace
            container_name = registry_repositories + "/" + k
            manifests = container_name + "/_manifests"
            tags = manifests + "/tags"
            # Delete the tag
            for item in v:
                del_tag = tags + "/" + item
                lib.rm(del_tag)
            # If no more tags, delete namespace
            subs = glob(tags + "/*")
            if len(subs) <= 0:
                lib.rm(namespace_path) 

    def collect(self):
        """Initiate the garbage collection."""
        index_files = glob(self._index_location + "/*.yml")
        # Go through index files
        for index_file in index_files:
            if "index_template" not in index_file:
                data = lib.load_yaml(index_file)
                if "Projects" not in data:
                    raise Exception("Invalid index file")
                for entry in data["Projects"]:
                    app_id = entry["app-id"]
                    job_id = entry["job-id"]
                    desired_tag = entry["desired-tag"]
                    # Initialize mismatch list to recieve data
                    container_name = str(app_id) + "/" + str(job_id)
                    if container_name not in self.index_containers:
                        #
                        self.index_containers[container_name] = []
                    self.index_containers[container_name].append(desired_tag)
        # Match index data with registry metadata
        for r_name, r_info in self._registry_info.tags.iteritems():
            r_tags = r_info["tags"]
            if r_name not in self.mismatched:
                self.mismatched[r_name] = []
            for item1 in r_tags:
                # On mismatch add to list
                if r_name in self.index_containers and item1 not in self.index_containers[r_name]:
                    self.mismatched[r_name].append(item1)
                if r_name not in self.index_containers:
                    self.mismatched[r_name].append(item1)
        self._delete_mismatched()
        print str.format("Removed images : \n{0}", self.mismatched)
