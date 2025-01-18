import os
import re
import json
import gzip
from multiprocessing import Process
from time import sleep
from platform import system
import yaml

class Wasabi():

    def __init__(self, debug: bool, disable_errors: bool, threads: int, regex: str, rx_contains: str, recursive: bool):
        self.debug = bool(debug)
        self.err = bool(disable_errors)
        self.threads = int(threads)
        self.regex = regex
        self.rx_contains = rx_contains
        self.recursive = recursive

        if self.regex != None and self.rx_contains != None:
            self.eprint("specifying a regex pattern and a contains flag is not allowed!")
            exit(1)
        
        if self.regex == None and self.rx_contains == None:
            self.eprint("regex pattern is empty")
            exit(1)

        if rx_contains != None:
            self.regex = f".*.{rx_contains}.*"
            self.rx_contains = None

    
    def calculate_threads_usage(self, paths: int) -> dict:
        '''Calcutaes the work that should evenly distrbuted to each thread.'''
        
        i_paths = paths
        i_threads = self.threads
        remainder = 1

        # Removes all occourences where paths / threads == is a decimal number.
        # Incrementing the number of paths to disbute to each thread will determine how much 
        # padding will need to be added to the full_paths list.
        while(remainder > 0):
            self.dprint(f"remainder: {remainder}")
            remainder = i_paths % i_threads

            if remainder > 0:
                i_paths += 1

        ch_per_th = i_paths / i_threads
        
        print("")
        self.dprint(f"Paths: {i_paths}")
        self.dprint(f"Padding: {i_paths - paths}")
        self.dprint(f"Threads: {i_threads}")
        self.dprint(f"Chunk_Size: {ch_per_th}")
        self.dprint(f"Remainder: {remainder}\n")

        output = {
            "paths": i_paths,
            "padding": i_paths - paths,
            "threads": i_threads,
            "chunk_size": ch_per_th,
            "remainder": remainder,
        }

        return output
    

    def create_thread_chunks(self, paths: list, data: dict) -> list[list[str]]:
        '''Splits all the directories to be scanned by yara into segments that will be assigned to each thread.'''
        
        output = []
        full_paths = paths

        n_threads = data["threads"]                 # The total number of threads.
        thread_chunk = int(data["chunk_size"])      # The number of items assigned to each thread.
        current_index = 0                           # Defines the start and end of each thread chunk.

        # Segments the paths in chunks that will be assigned to each thread.
        for i in range(n_threads):
            if i == 0:
                output.append(full_paths[0:thread_chunk])
            elif i > 0:
                output.append(full_paths[current_index:current_index + thread_chunk])
            
            current_index += thread_chunk
        
        for i in range(len(output)):
            self.dprint(f"Index[{i}] Chunk size per thread: {len(output[i])}")

        return output


    def eprint(self, message: str):
        if self.error == False:
            print(f"Error: {message}")
        else:
            return


    def dprint(self, message: str):
        if self.debug == True:
            print(f"debug => {message}")
        else:
            return


    def extract_gzip(filename: str):
        zip = None
        buffer = ""

        try:
            zip = gzip.GzipFile(filename, "rb").read()
            buffer = zip.decode("utf8")
            buffer = Wasabi.prettify_json(buffer)
        except Exception as e:
            return None
                
        return buffer


    def prettify_json(content: str) -> str:
        output = ""
        data = ""

        try:
            data = json.loads(content)
        except Exception as e:
            # self.eprint(e)
            return None
        
        try:
            output = json.dumps(data, indent=4)
        except Exception:
            # self.eprint(e)
            return None
        
        return output


    def match_string(pattern: str, string: str) -> list[str]:
        out = ""
        
        try:
            out = re.findall(pattern, string)
        except Exception as e:
            return None

        return out


    def match_file_path(self, pattern, string) -> str:
        out = re.search(pattern, string)

        if out != None:
            out = out.group(0)
        else:
            return None

        return out


    def is_relative_path(self, filename):
        if filename == None:
            self.eprint(f"the provided filename {filename} does not exist")
            return False
        
        if os.path.isabs(filename) == False:
            return True
        else:
            return False


    def recursive_directory_search(self, pathname: str, sh_extensions=True):
        output_files = []
        
        for root, dirs, files in os.walk(pathname, topdown=sh_extensions):
            
            for name in files:
                filename = os.path.join(root, name)

                if self.debug == True:
                    self.dprint(filename)

                output_files.append(filename)
            
            for name in dirs:
                dir_name = os.path.join(root, name)

                if self.debug == True:
                    self.dprint(dir_name)

        return output_files


    def parse_file(self, args):
        path_name = args.path
        pattern = self.regex

        if path_name == None:
            self.eprint("no file path was specified")
            return

        full_path = os.getcwd()
        if os.path.exists(path_name) == False:
            self.eprint(f"the provided filename {path_name} does not exist")
            return
        
        if self.is_relative_path(path_name) == True:
            full_path = self.join_path([full_path, path_name])
        else:
            full_path = path_name

        buffer = ""
        
        if full_path.endswith(".gz"):
            buffer = Wasabi.extract_gzip(full_path)
        else:
            buffer = Wasabi.catch_read_exception(full_path)

        results = Wasabi.match_string(pattern, buffer)

        for i in results:
            print({str(i).strip()})


    def read_file(filename: str) -> str:
        buffer = ""

        with open(filename, "r") as f:
            buffer = f.read()

        return buffer


    def catch_read_exception(path: str) -> str:
        output = ""
        
        try:
            output = Wasabi.read_file(path)
            return output
        except Exception as e:
            # self.eprint(e)
            return


    def start_threads(self, target_function: any, path_name: str, pattern: str, recursive: bool):
        paths = []
        
        if recursive == True:
            paths = self.recursive_directory_search(path_name)
        else:
            temp_paths = os.listdir(path_name)
            
            for i in temp_paths:
                full_path = os.path.join(path_name, i)
                
                if full_path:
                    paths.append(full_path)

            if self.debug == True:
                for i in paths:
                    self.dprint(i)

        
        thread_info = self.calculate_threads_usage(len(paths))
        chunks = self.create_thread_chunks(paths, thread_info)
        
        handles = []
        
        for i in chunks:
            handle = Process(
                target=target_function,
                args=(i, pattern)
            )

            handle.start()
            handles.append(handle)
            sleep(0.3)

        for i in handles:
            i.join()
            
            self.dprint("joining thread to main")

        return


    def read_file_contents(self, path_name: str, pattern: str):
        paths = self.recursive_directory_search(path_name)

        for p in paths:
            contents = ""
            
            if str(p).endswith(".gz"):
                contents = Wasabi.extract_gzip(p)
            else:
                contents = Wasabi.catch_read_exception(p)
                if contents == None:
                    continue

            print(f"contents -> {contents} path -> {p}")
            check_contents = Wasabi.match_string(pattern, contents)

            if check_contents != None and check_contents != []:
                print(f"\n{p}")
                
                for i in check_contents:
                    print(i)


    def th_read_file_contents(paths: list[str], pattern: str):
        for p in paths:
            contents = ""
            
            if str(p).endswith(".gz"):
                contents = Wasabi.extract_gzip(p)
            else:
                contents = Wasabi.catch_read_exception(p)
                if contents == None:
                    continue

            check_contents = Wasabi.match_string(pattern, contents)

            if check_contents != None and check_contents != []:
                print(f"\n{p}")
                
                for i in check_contents:                    
                    print(i)


    def list_file_names(self, path_name: str, pattern: str):
        paths = self.recursive_directory_search(path_name)

        for p in paths:
            check_name = Wasabi.match_string(pattern, p)
            
            if check_name != None and check_name != "":    
                for i in check_name:
                    print(i)


    def th_list_file_names(paths: list[str], pattern: str):
        for p in paths:
            check_name = Wasabi.match_string(pattern, p)
            
            if check_name != None and check_name != "":    
                for i in check_name:
                    print(i)


    def load_yaml(file_name: str) -> dict[str]:
        data = None

        try:
            data = yaml.safe_load(file_name)
            return data
        except Exception as e:
            return None
        

    def catch_key_error(data: dict, key: str) -> str:
        out = None

        try:
            out = data[key]
            return out
        except Exception as e:
            return None


    def join_path(self, strings: list) -> str:
        delim = ""
        out = ""

        if system().lower() == "windows":
            delim = "\\"
        else:
            delim = "/"

        counter = 1
        for i in strings:

            if counter == len(strings):
                out += i
                break
            
            elif counter < len(strings):
                out += i + delim

            counter += 1

        return out


    def parse_directory(self, args):
        path_name = args.path
        pattern = self.regex
        recursive = self.recursive

        self.dprint(pattern)

        read_file_cnt = bool(args.open_files)
        show_file_names = bool(args.names)
        
        if path_name == None:
            self.eprint("no directory path was specified")
            return

        if read_file_cnt == True and show_file_names == True:
            self.eprint("--open_files and --names cannot both be true!")
            return

        full_path = os.getcwd()
        if self.is_relative_path(path_name) == True:
            full_path = self.join_path([full_path, path_name])
        
        if os.path.exists(path_name) == False:
            self.eprint(f"the provided filename {path_name} does not exist")
            return
        
        if read_file_cnt == False and show_file_names == False:
            self.eprint("must provide either --open-files or --names")
            return
        
        if read_file_cnt == True:

            if self.threads <= 1:
                self.read_file_contents(path_name, pattern)
            elif self.threads > 1:
                self.start_threads(
                    Wasabi.th_read_file_contents,
                    path_name,
                    pattern,
                    recursive
                )

        elif show_file_names == True:

            if self.threads <= 1:
                self.list_file_names(path_name, pattern)
            elif self.threads > 1:
                self.start_threads(
                    Wasabi.th_list_file_names,
                    path_name,
                    pattern,
                    recursive
                )
