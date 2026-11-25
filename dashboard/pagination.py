from django.core.paginator import Paginator


def paginate_queryset(request, queryset, per_page=10, page_param="page"):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get(page_param))
    return page_obj, page_obj.object_list
