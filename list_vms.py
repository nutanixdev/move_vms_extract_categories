"""
list_vms.py - list all VMs in a cluster that are
assigned to a specific category
can be used to list VMs that are NOT assigned to 
any category by specifying {} in the params file
"""

from dataclasses import dataclass
import requests
import urllib3
import argparse
import getpass
import json
from base64 import b64encode
import sys
import os
import time
from requests.auth import HTTPBasicAuth
import smtplib
from email.message import EmailMessage


@dataclass
class RequestParameters:
    """
    dataclass to hold the parameters of our API request
    this is not strictly required but can make
    our requests cleaner
    """
    uri: str
    username: str
    password: str
    payload: list
    method: str


class RequestResponse:
    """
    class to hold the response from our
    requests
    again, not strictly necessary but can
    make things cleaner later
    """

    def __init__(self):
        self.code = 0
        self.message = ""
        self.json = ""
        self.details = ""

    def __repr__(self):
        '''
        decent __repr__ for debuggability
        this is something recommended by Raymond Hettinger
        it is good practice and should be left here
        unless there's a good reason to remove it
        '''
        return (f'{self.__class__.__name__}('
                f'code={self.code},'
                f'message={self.message},'
                f'json={self.json},'
                f'details={self.details})')


class RESTClient:
    """
    the RESTClient class carries out the actual API request
    by 'packaging' these functions into a dedicated class,
    we can re-use instances of this class, resulting in removal
    of unnecessary code repetition and resources
    """

    def __init__(self, parameters: RequestParameters):
        """
        class constructor
        because this is a simple class, we only have a single
        instance variable, 'params', that holds the parameters
        relevant to this request
        """
        self.params = parameters

    def __repr__(self):
        '''
        decent __repr__ for debuggability
        this is something recommended by Raymond Hettinger
        '''
        return (f'{self.__class__.__name__}('
                f'username={self.params.username},password=<hidden>,'
                f'uri={self.params.uri}',
                f'payload={self.params.payload})')

    def send_request(self):
        """
        this is the main method that carries out the request
        basic exception handling is managed here, as well as
        returning the response (success or fail), as an instance
        of our RequestResponse dataclass
        """
        response = RequestResponse()

        """
        setup the HTTP Basic Authorization header based on the
        supplied username and password
        done this way so that passwords are not supplied on the command line
        """
        username = self.params.username
        password = self.params.password
        encoded_credentials = b64encode(
            bytes(f"{username}:{password}", encoding="ascii")
        ).decode("ascii")
        auth_header = f"Basic {encoded_credentials}"

        """
        setup the request headers
        note the use of {auth_header} i.e. the Basic Authorization
        credentials we setup earlier
        """

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"{auth_header}",
            "cache-control": "no-cache",
        }

        try:

            if self.params.method == 'get':
                # submit a GET request
                api_request = requests.get(
                    self.params.uri,
                    headers=headers,
                    auth=HTTPBasicAuth(username, password),
                    timeout=60,
                    verify=False
                )
            elif self.params.method == 'post' or self.params.method == 'put':
                # submit a POST request
                api_request = requests.post(
                    self.params.uri,
                    headers=headers,
                    auth=HTTPBasicAuth(username, password),
                    timeout=60,
                    verify=False,
                    data=self.params.payload
                )
            # if no exceptions occur here, we can process the response
            response.code = api_request.status_code
            response.message = "Request submitted successfully."
            response.json = api_request.json()
            response.details = "N/A"
        except requests.exceptions.ConnectTimeout:
            # timeout while connecting to the specified IP address or FQDN
            response.code = -99
            response.message = f"Connection has timed out."
            response.details = "Exception: requests.exceptions.ConnectTimeout"
        except urllib3.exceptions.ConnectTimeoutError:
            # timeout while connecting to the specified IP address or FQDN
            response.code = -99
            response.message = f"Connection has timed out."
            response.details = "urllib3.exceptions.ConnectTimeoutError"
        except requests.exceptions.MissingSchema:
            # potentially bad URL
            response.code = -99
            response.message = "Missing URL schema/bad URL."
            response.details = "N/A"
        except Exception as _e:
            """
            unhandled exception
            ... don't do this in production
            """
            response.code = -99
            response.message = "An unhandled exception has occurred."
            response.details = _e

        return response


# get the time the script started
start_time = time.time()

"""
suppress warnings about insecure connections
you probably shouldn't do this in production
"""
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""
setup our command line parameters
for this example we only require the a single parameter
- the name of the JSON file that contains our request parameters
this is a very clean way of passing parameters to this sort of
script, without the need for excessive parameters on the command line
"""
parser = argparse.ArgumentParser()
parser.add_argument("json", help="JSON file containing query parameters")
args = parser.parse_args()

"""
try and read the JSON parameters from the supplied file
"""
json_data = ""
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
    with open(f"{script_dir}/{args.json}", "r") as params:
        json_data = json.load(params)
    pc_ip = json_data["pc_ip"]
    category = json_data["category"]
    user = json_data["username"]
    email_settings = json_data["email_settings"]
except FileNotFoundError:
    print(f"{args.json} parameters file not found.")
    sys.exit()
except json.decoder.JSONDecodeError:
    print("\nThe provided JSON file cannot be parsed.")
    print("Please check the file contains valid JSON, then try again.\n")
    sys.exit()
except KeyError:
    print('Required key was not found in the specified JSON parameters file.  Exiting ...')
    sys.exit()

try:
    #######################################
    # gather some info before carrying on #
    #######################################

    # for this test script we're just going to assume both PC authenticates as 'admin'
    print(f'\nUsername: {user}')
    print(f'Category: {category}\n')

    # get the PC password
    pc_password = getpass.getpass(
        prompt="Please enter your Prism Central password: ", stream=None
    )

    all_vms = []

    # setup the parameters for the initial request
    parameters = RequestParameters(
        uri=f"https://{pc_ip}:9440/api/nutanix/v3/vms/list",
        username=user,
        password=pc_password,
        payload='{"kind":"vm","length":500,"offset":0}',
        method='post'
    )

    """
    this instance of our RESTClient class will be used for this and
    all subsequent requests, if they are required
    i.e. if the cluster has >500 VMs
    """
    rest_client = RESTClient(parameters)

    # send the initial request
    response = rest_client.send_request()

    """
    see if the request was valid
    for this code sample, a return code of -99 indicates something
    went wrong
    all other codes are standard HTTP codes
    """
    if (response.code == 200) or (response.code == 201):
        """
        the initial request was successful
        now we need to check for the number of VMs, since this
        script is specifically written to be compatible with
        'large' clusters
        """

        """
        first, grab the number of VMs from this initial request
        we'll use this number to calculate how many interations
        to make in upcoming requests
        """

        vm_count = response.json["metadata"]["total_matches"]
        vms_in_request = response.json["metadata"]["length"]
        # use a Python list comprehension to quickly extract the VMs that have no categories assigned
        all_vms = all_vms + [ vm for vm in response.json["entities"] if vm['metadata']['categories'] == category ]

        print(f"Total VMs in this cluster: {vm_count}")
        print(f"Total VMs in this request (iteration #0): {vms_in_request}")

        """
        the nutanix 'vms' API will only ever return 500 VMs
        this will apply even if the 'length' parameter is set to a value >500
        """
        if vm_count > 500:
            """
            at this point you would "do something" based on knowing there are
            >500 VMs in the cluster

            for example, you could iterate over the VMs, collecting
            the necessary information, etc

            for our demo, we've already got a response containing
            information about the first 500 VMs so there's no need
            to submit a request for the first 500 again
            (expensive and unnecessary)
            """
            print("There are more than 500 VMs in this cluster.")
            print(
                "Multiple iterations/requests are required "
                + "to collect all VM information."
            )

            """
            by immediately setting the offset to 500, subsequent requests
            will start from VM at index 501 and go forward from there
            again, we've already got the response above for the first 500 VMs

            we're using chunks of 500 VMs here, but in a real app there's no
            reason why this chunk needs to be 500
            note, however, the 500 is the MAXIMUM number of VMs returned in a
            single request
            """

            max_vms_in_response = 500
            offset = max_vms_in_response

            """
            work out how many interations are required
            simple math based on the number of times
            a 500 VM response will be received
            """
            iterations = vm_count // max_vms_in_response
            print(
                "Total iterations required, including the "
                + f"initial request: {iterations + 1}"
            )

            """
            starting at 1 here because we've already completed iteration '0'
            """
            iterator = 1
            while iterator <= iterations:
                iterator_parameters = RequestParameters(
                    uri=f"https://{pc_ip}:9440/api/nutanix/v3/vms/list",
                    username=user,
                    password=pc_password,
                    payload=f'{{"kind":"vm","length":500,"offset":{offset}}}',
                    method='post'
                )

                # set the parameters for the next request, then submit it
                rest_client.params = iterator_parameters
                iterator_response = rest_client.send_request()

                # check to see what response we got back
                if (iterator_response.code == 200) or (iterator_response.code == 201):
                    iterator_vm_count = iterator_response.json["metadata"]["length"]
                    # use a Python list comprehension to quickly extract the VMs that have no categories assigned
                    all_vms = all_vms + [ vm for vm in iterator_response.json["entities"] if vm['metadata']['categories'] == category ]
                    print(
                        "Total VMs in this request "
                        + f"(iteration #{iterator}): {iterator_vm_count}"
                    )
                else:
                    '''
                    an error of some sort occurred during the request
                    show the code and related messages for troubleshooting purposes
                    '''
                    print(f'Response code: {iterator_response.code}')
                    print(f'Message: {response.message}')
                    print(f'Details: {response.details}')

                '''
                increment our variables so we aren't hitting infinite loops
                and getting the same batch of VMs again
                '''
                iterator += 1
                offset += max_vms_in_response

        else:
            print("There are fewer than 500 VMs in this cluster")
            print(
                "Only a single iteration/request is required to collect "
                + "all VM information"
            )

        print(f'\nTotal VMs that are assigned to the specified category: {len(all_vms)}.')
        # print and build the list of VMs without categories
        email_body = ""
        for vm in all_vms:
            line_for_email = f"VM name: {vm['status']['name']} | Cluster: {vm['status']['cluster_reference']['name']}"
            email_body = email_body + f'{line_for_email}\n'

        ############################################################
        # prepare the email body that will contain the list of VMs #
        ############################################################

        print('Preparing email ...')
        category_data = EmailMessage()
        category_data.set_content(email_body)
        category_data['Subject'] = email_settings['subject']
        category_data['From'] = email_settings['sender']
        category_data['To'] = email_settings['recipient']
        print('Done.')
        print('Sending email ...')
        smtp_connection = smtplib.SMTP(
            email_settings['smtp_server'],
            email_settings['smtp_port']
        )
        if email_settings['require_ehlo']:
            smtp_connection.ehlo()
        if email_settings['require_tls']:
            smtp_connection.starttls()
        smtp_connection.login(
            email_settings['smtp_user'],
            email_settings['smtp_password']
        )
        smtp_connection.send_message(category_data)
        smtp_connection.quit()
        print('Done.')
        print('\nAll operations finished (%.2f seconds)' % (time.time() - start_time))

    elif response.code == -99:
        # indicate that we've caught an exception and
        print("\nScript threw custom error code -99.")
        print(f"{response.message}\n")
        print(f"Details: {response.details}\n")
    else:
        print(f"HTTP code: {response.code}\n")
        print(f"Message: {response.message}\n")
        print(f"JSON: {response.json}\n")
        print(f"Details: {response.details}")


except KeyError:
    """
    in this instance, a KeyError most likely indicates a malformed
    or incomplete JSON parameters file
    """
    print("\nThe provided JSON file either cannot be parsed")
    print("or does not contain the required parameters.")
    print("Please check the file contains cluster_ip and")
    print("username parameters, then try again.\n")
    print(ex)
except Exception as ex:
    print(ex)

"""
wait for the enter key before continuing
this is to prevent terminal flashing if being run inside VS Code, for example
"""
input("\nPress ENTER to exit.")
