# -*- coding: utf-8 -*-

from modernrpc.core import rpc_method, REQUEST_KEY

from tcms.core.utils import string_to_list, form_errors_to_list
from tcms.management.models import TestTag
from tcms.testplans.models import TestPlan, TCMSEnvPlanMap
from tcms.testcases.models import TestCase, TestCasePlan

from tcms.xmlrpc.decorators import permissions_required
from tcms.xmlrpc.utils import pre_process_ids

__all__ = (
    'add_case',
    'remove_case',

    'filter',

    'add_tag',
    'create',
    'get_tags',
    'remove_tag',
    'store_text',
    'update',
)


@permissions_required('testplans.add_testplantag')
@rpc_method(name='TestPlan.add_tag')
def add_tag(plan_ids, tags):
    """
    Description: Add one or more tags to the selected test plans.

    Params:      $plan_ids - Integer/Array/String: An integer representing the ID of the plan
                      in the database,
                      an arry of plan_ids, or a string of comma separated plan_ids.

                  $tags - String/Array - A single tag, an array of tags,
                      or a comma separated list of tags.

    Returns:     Array: empty on success or an array of hashes with failure
                  codes if a failure occured.

    Example:
    # Add tag 'foobar' to plan 1234
    >>> TestPlan.add_tag(1234, 'foobar')
    # Add tag list ['foo', 'bar'] to plan list [12345, 67890]
    >>> TestPlan.add_tag([12345, 67890], ['foo', 'bar'])
    # Add tag list ['foo', 'bar'] to plan list [12345, 67890] with String
    >>> TestPlan.add_tag('12345, 67890', 'foo, bar')
    """
    # FIXME: this could be optimized to reduce possible huge number of SQLs

    tps = TestPlan.objects.filter(plan_id__in=pre_process_ids(value=plan_ids))

    if not isinstance(tags, (str, list)):
        raise ValueError('Parameter tags must be a string or list(string)')

    tags = string_to_list(tags)

    for tag in tags:
        t, c = TestTag.objects.get_or_create(name=tag)
        for tp in tps.iterator():
            tp.add_tag(tag=t)

    return


@permissions_required('testplans.add_testplan')
@rpc_method(name='TestPlan.create')
def create(values, **kwargs):
    """
    Description: Creates a new Test Plan object and stores it in the database.

    Params:      $values - Hash: A reference to a hash with keys and values
                  matching the fields of the test plan to be created.
     +--------------------------+---------+-----------+-------------------------------------------+
     | Field                    | Type    | Null      | Description                               |
     +--------------------------+---------+-----------+-------------------------------------------+
     | product                  | Integer | Required  | ID of product                             |
     | name                     | String  | Required  |                                           |
     | type                     | Integer | Required  | ID of plan type                           |
     | product_version          | Integer | Required  | ID of version, product_version(recommend),|
     | (default_product_version)|         |           | default_product_version will be deprecated|
     |                          |         |           | in future release.                        |
     | text                     | String  | Required  | Plan documents, HTML acceptable.          |
     | parent                   | Integer | Optional  | Parent plan ID                            |
     | is_active                | Boolean | Optional  | 0: Archived 1: Active (Default 0)         |
     +--------------------------+---------+-----------+-------------------------------------------+

    Returns:     The newly created object hash.

    Example:
    # Minimal test case parameters
    >>> values = {
        'product': 61,
        'name': 'Testplan foobar',
        'type': 1,
        'parent_id': 150,
        'default_product_version': 93,
        'text':'Testing TCMS',
    }
    >>> TestPlan.create(values)
    """
    from tcms.xmlrpc.forms import NewPlanForm

    if values.get('default_product_version'):
        values['product_version'] = values.pop('default_product_version')

    if not values.get('product'):
        raise ValueError('Value of product is required')

    form = NewPlanForm(values)
    form.populate(product_id=values['product'])

    if form.is_valid():
        request = kwargs.get(REQUEST_KEY)
        tp = TestPlan.objects.create(
            product=form.cleaned_data['product'],
            name=form.cleaned_data['name'],
            type=form.cleaned_data['type'],
            author=request.user,
            product_version=form.cleaned_data['product_version'],
            parent=form.cleaned_data['parent'],
            is_active=form.cleaned_data['is_active']
        )

        tp.add_text(
            author=request.user,
            plan_text=values['text'],
        )

        return tp.serialize()
    else:
        raise ValueError(form_errors_to_list(form))


@rpc_method(name='TestPlan.filter')
def filter(query={}):
    """
    .. function:: XML-RPC TestPlan.filter(query)

        Perform a search and return the resulting list of test plans.

        :param query: Field lookups for :class:`tcms.testplans.models.TestPlan`
        :type query: dict
        :return: List of serialized :class:`tcms.testplans.models.TestPlan` objects
        :rtype: list(dict)
    """
    results = []
    for plan in TestPlan.objects.filter(**query):
        serialized_plan = plan.serialize()

        # the text for this TestPlan
        latest_text = plan.latest_text()
        if latest_text:
            serialized_plan['text'] = latest_text.plan_text

        results.append(serialized_plan)

    return results


@rpc_method(name='TestPlan.get_tags')
def get_tags(plan_id):
    """
    Description: Get the list of tags attached to this plan.

    Params:      $plan_id - Integer An integer representing the ID of this plan in the database

    Returns:     Array: An array of tag object hashes.

    Example:
    >>> TestPlan.get_tags(137)
    """
    test_plan = TestPlan.objects.get(plan_id=plan_id)

    tag_ids = test_plan.tag.values_list('id', flat=True)
    query = {'id__in': tag_ids}
    return TestTag.to_xmlrpc(query)


@permissions_required('testplans.delete_testplantag')
@rpc_method(name='TestPlan.remove_tag')
def remove_tag(plan_ids, tags):
    """
    Description: Remove a tag from a plan.

    Params:      $plan_ids - Integer/Array/String: An integer or alias representing the ID
                                                   in the database, an array of plan_ids,
                                                   or a string of comma separated plan_ids.

                 $tag - String - A single tag to be removed.

    Returns:     Array: Empty on success.

    Example:
    # Remove tag 'foo' from plan 1234
    >>> TestPlan.remove_tag(1234, 'foo')
    # Remove tag 'foo' and 'bar' from plan list [56789, 12345]
    >>> TestPlan.remove_tag([56789, 12345], ['foo', 'bar'])
    # Remove tag 'foo' and 'bar' from plan list '56789, 12345' with String
    >>> TestPlan.remove_tag('56789, 12345', 'foo, bar')
    """
    from tcms.management.models import TestTag

    test_plans = TestPlan.objects.filter(
        plan_id__in=pre_process_ids(value=plan_ids)
    )

    if not isinstance(tags, (str, list)):
        raise ValueError('Parameter tags must be a string or list(string)')

    test_tags = TestTag.objects.filter(
        name__in=string_to_list(tags)
    )

    for test_plan in test_plans.iterator():
        for test_tag in test_tags.iterator():
            test_plan.remove_tag(tag=test_tag)


@permissions_required('testplans.add_testplantext')
@rpc_method(name='TestPlan.store_text')
def store_text(plan_id, text, **kwargs):
    """
    Description: Update the document field of a plan.

    Params:      $plan_id - Integer: An integer representing the ID of this plan in the database.
                 $text - String: Text for the document. Can contain HTML.
                 [$author] = Integer: (OPTIONAL) The numeric ID or the login of the author.
                      Defaults to logged in user.

    Returns:     Hash: The new text object hash.

    Example:
    >>> TestPlan.store_text(1234, 'Plan Text', 2207)
    """
    from django.contrib.auth.models import User

    tp = TestPlan.objects.get(plan_id=plan_id)

    author = kwargs.get('author', None)
    if author:
        author = User.objects.get(id=author)
    else:
        request = kwargs.get(REQUEST_KEY)
        author = request.user

    return tp.add_text(
        author=author,
        plan_text=text and text.strip(),
    ).serialize()


@permissions_required('testplans.change_testplan')
@rpc_method(name='TestPlan.update')
def update(plan_ids, values):
    """
    Description: Updates the fields of the selected test plan.

    Params:      $plan_ids - Integer: A single (or list of) TestPlan ID.

                 $values - Hash of keys matching TestPlan fields and the new values
                           to set each field to.
      +---------------------------+----------------+--------------------------------------------+
      | Field                     | Type           | Description                                |
      +---------------------------+----------------+--------------------------------------------+
      | product                   | Integer        | ID of product                              |
      | name                      | String         |                                            |
      | type                      | Integer        | ID of plan type                            |
      | product_version           | Integer        | ID of version, product_version(recommend), |
      |  (default_product_version)|                | default_product_version will be deprecated |
      |                           |                | in future release.                         |
      | owner                     | String/Integer | user_name/user_id                          |
      | parent                    | Integer        | Parent plan ID                             |
      | is_active                 | Boolean        | True/False                                 |
      | env_group                 | Integer        | New environment group ID                   |
      +---------------------------+-------------------------------------------------------------+

    Returns:     Hash: The updated test plan object.

    Example:
    # Update product to 61 for plan 207 and 208
    >>> TestPlan.update([207, 208], {'product': 61})
    """
    from tcms.xmlrpc.forms import EditPlanForm

    if values.get('default_product_version'):
        values['product_version'] = values.pop('default_product_version')

    form = EditPlanForm(values)

    if values.get('product_version') and not values.get('product'):
        raise ValueError('Field "product" is required by product_version')

    if values.get('product') and not values.get('product_version'):
        raise ValueError('Field "product_version" is required by product')

    if values.get('product_version') and values.get('product'):
        form.populate(product_id=values['product'])

    plan_ids = pre_process_ids(value=plan_ids)
    tps = TestPlan.objects.filter(pk__in=plan_ids)

    if form.is_valid():
        _values = dict()
        if form.cleaned_data['name']:
            _values['name'] = form.cleaned_data['name']

        if form.cleaned_data['type']:
            _values['type'] = form.cleaned_data['type']

        if form.cleaned_data['product']:
            _values['product'] = form.cleaned_data['product']

        if form.cleaned_data['product_version']:
            _values['product_version'] = form.cleaned_data[
                'product_version']

        if form.cleaned_data['owner']:
            _values['owner'] = form.cleaned_data['owner']

        if form.cleaned_data['parent']:
            _values['parent'] = form.cleaned_data['parent']

        if not (values.get('is_active') is None):
            _values['is_active'] = form.cleaned_data['is_active']

        tps.update(**_values)

        # requested to update environment group for selected test plans
        if form.cleaned_data['env_group']:
            # prepare the list of new objects to be inserted into DB
            new_objects = [
                TCMSEnvPlanMap(
                    plan_id=plan_pk,
                    group_id=form.cleaned_data['env_group'].pk
                ) for plan_pk in plan_ids
            ]

            # first delete the old values (b/c many-to-many I presume ?)
            TCMSEnvPlanMap.objects.filter(plan__in=plan_ids).delete()
            # then create all objects with 1 INSERT
            TCMSEnvPlanMap.objects.bulk_create(new_objects)
    else:
        raise ValueError(form_errors_to_list(form))

    query = {'pk__in': tps.values_list('pk', flat=True)}
    return TestPlan.to_xmlrpc(query)


@permissions_required('testcases.add_testcaseplan')
@rpc_method(name='TestPlan.add_case')
def add_case(plan_id, case_id):
    """
    .. function:: XML-RPC TestPlan.add_case(plan_id, case_id)

        Link test case to the given plan.

        :param plan_id: PK of TestPlan to modify
        :type plan_id: int
        :param case_id: PK of TestCase to be added to plan
        :type case_id: int
        :return: None
        :raises: TestPlan.DoesNotExit or TestCase.DoesNotExist if objects specified
                 by PKs are missing
        :raises: PermissionDenied if missing *testcases.add_testcaseplan* permission
    """
    plan = TestPlan.objects.get(pk=plan_id)
    case = TestCase.objects.get(pk=case_id)
    plan.add_case(case)


@permissions_required('testcases.delete_testcaseplan')
@rpc_method(name='TestPlan.remove_case')
def remove_case(plan_id, case_id):
    """
    .. function:: XML-RPC TestPlan.remove_case(plan_id, case_id)

        Unlink a test case from the given plan.

        :param plan_id: PK of TestPlan to modify
        :type plan_id: int
        :param case_id: PK of TestCase to be removed from plan
        :type case_id: int
        :return: None
        :raises: PermissionDenied if missing *testcases.delete_testcaseplan* permission
    """
    TestCasePlan.objects.filter(case=case_id, plan=plan_id).delete()
