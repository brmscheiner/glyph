import ast
import printing as pr
import importAnalysis as ia
import copy

''' known bugs:

    imp_mods[scanner\scanner.py] contains elements even though 
    scanner\scanner.py imports no modules (only from style imports)
    
    '''

def show(node):
    ast.dump(node)

def isImport(node):
    pass

def getCurrentClass(stack):
    for x in stack:
        if isinstance(x, ast.ClassDef):
            return x
    return None

def getSourceFnDef(stack,fdefs,path):
    '''VERY VERY SLOW'''
    found = False
    for x in stack:
        if isinstance(x, ast.FunctionDef):
            for y in fdefs[path]:
                if ast.dump(x)==ast.dump(y): #probably causing the slowness
                    found = True
                    return y
            raise
    if not found:
        for y in fdefs[path]:
            if y.name=='body':
                return y
    raise
    
def getTargetFnDef(node,path,fdefs,imp_funcs,imp_mods,imp_class_strs):
    ''' What about method calls like hat.compare(sombrero)'''
    #CASE 1: calling function inside namespace, like foo(x) or randint(x,y)
    if isinstance(node.func,ast.Name):
        if path in fdefs:
            for x in fdefs[path]:
                if node.func.id == x.name: # Need to go back through and compare parent classes.
                    return x
        if path in imp_funcs:
            for x in imp_funcs[path]:
                if node.func.id == x.name: # Need to go back through and compare parent classes.
                    return x
        return None # 200 instances!
        
    # CASE 2: # calling function outside namespace, like random.randint(x,y)
    elif isinstance(node.func,ast.Attribute):
        try:
            obj    = node.func.value.id
            method = node.func.attr
        except AttributeError:
            return None #130 instances!
            
        # CASE 2A: # calling module.function
        for modpath in imp_mods[path]:
            if not modpath:
                break
            elif obj+'.py' in modpath:
                matches = [x for x in fdefs[modpath] if x.name==method]
                if matches:
                    if len(matches)>1:
                        print("multiple matches found for "+method)
                    return matches[0]
                else:
                    return None
                    
        # CASE 2B: # calling class.method
            # once we match the call to an object in imp_class_strs,
            # we will still have to look for the associated call in 
            # fdefs[mod] 
    return None

def calcFnWeight(node):
    '''Calculates the weight of a function definition by recursively counting 
    its child nodes in the AST. Note that the tree traversal will become 
    O(n^2) instead of O(n) if this feature is enabled.'''
    stack = [node]
    count = 0
    while len(stack) > 0:
        node = stack.pop()
        children = [x for x in ast.iter_child_nodes(node)]
        count += len(children)
        stack = stack + children
    return count
                
def traversal(root):
    '''For each subtree, evaluate the deepest nodes first. Then evaluate the
    next-deepest nodes and move on to the next subtree.'''
    stack = [root]
    while len(stack) > 0:
        node = stack.pop()
        if hasattr(node,'children'):
            if node.children == set():
                try:
                    stack[-1].children.remove(node)
                except:
                    pass
                yield (node,stack)
            else:
                childnode = node.children.pop()
                stack += [node,childnode]
        else: 
            children = [x for x in ast.iter_child_nodes(node)]
            node.children = set(children)
            stack.append(node)

def formatBodyNode(root,path):
    '''Format the root node for use as the body node.'''
    body        = root
    body.name   = "body"
    body.weight = calcFnWeight(body)
    body.path   = path
    body.pclass = None
    return body

def formatFunctionNode(node,path,stack):
    '''Add some helpful attributes to node.'''
    #node.name is already defined by AST module
    node.weight = calcFnWeight(node)
    node.path   = path
    node.pclass = getCurrentClass(stack)
    return node

def firstPass(ASTs):
    '''Return a dictionary of function definition nodes, a dictionary of  
    imported object names and a dictionary of imported module names. All three 
    dictionaries use source file paths as keys.'''
    fdefs=dict()
    imp_obj_strs=dict()
    imp_mods=dict()
    for (root,path) in ASTs:
        fdefs[path] = []
        fdefs[path].append(formatBodyNode(root,path))
        imp_obj_strs[path] = []
        imp_mods[path] = []
        for (node,stack) in traversal(root):
            if isinstance(node,ast.FunctionDef):
                fdefs[path].append(formatFunctionNode(node,path,stack))
            elif isinstance(node,ast.ImportFrom):
                module = ia.getImportFromModule(node,path)
                if module:
                    fn_names = ia.getImportFromObjects(node)
                    for fn_name in fn_names:
                        imp_obj_strs[path].append((module,fn_name))
                else:
                    print("No module found "+ast.dump(node))
            elif isinstance(node,ast.Import):
                module = ia.getImportModule(node,path)
                imp_mods[path].append(module)
    return fdefs,imp_obj_strs,imp_mods

def matchImpObjStrs(fdefs,imp_obj_strs):
    '''returns imp_funcs, a dictionary with filepath keys that contains lists 
    of function objects that were imported using "from __ import __" style 
    syntax and imp_class_strs, a dictionary with filepath keys that contains 
    lists of non-function objects that were imported using 
    "from __ import ___" style syntax'''
    imp_funcs=dict()
    imp_class_strs=dict()
    for source in imp_obj_strs:
        if imp_obj_strs[source]==[]:
            break
        imp_funcs[source]=[]
        imp_class_strs[source]=[]
        for (mod,func) in imp_obj_strs[source]:
            if mod not in fdefs:
                print(mod+" is not part of the project.")
                break
            if func=='*':
                all_fns = [x for x in fdefs[mod] if x.name!='body']
                imp_funcs[source] += all_fns
                '''note: must add all available classes in mod to imported list'''
                #imp_class_strs[source] += all_available_classes
            else:
                fn_node = [x for x in fdefs[mod] if x.name==func]
                if fn_node==[]:
                    imp_class_strs[source].append((mod,func))
                else:
                    assert len(fn_node)==1
                    imp_funcs[source] += fn_node
    return imp_funcs,imp_class_strs
    
def matchImpClassStrs(fdefs,imp_class_strs):
    imp_methods=dict()
    for source in imp_class_strs:
        if imp_class_strs[source]==[]:
            break
        imp_methods[source]=[]
        for (mod,clss) in imp_class_strs[source]:
            if mod not in fdefs:
                print(mod+" is not part of the project.")
                break
            valid = lambda x: hasattr(x,"pclass") and hasattr(x.pclass,"name")
            classes = [x.pclass.name for x in fdefs[mod] if valid(x)] #all functions in fdefs with parent classes 
            matches = [x for x in fdefs[mod] if x.pclass==clss]
            print(clss)
            print([x.pclass.name for x in fdefs[mod] if valid(x)])
    return imp_methods
        

def secondPass(ASTs,fdefs,imp_funcs,imp_mods,imp_class_strs):
    nfound=0
    calls=[]
    for (root,path) in ASTs:
        for (node,stack) in traversal(root):
            if isinstance(node, ast.Call):
                #node.source = getSourceFnDef(stack,fdefs,path)
                node.target = getTargetFnDef(node,path,fdefs,
                                             imp_funcs,imp_mods,imp_class_strs)
                if node.target: 
                    nfound+=1
                calls.append(node)
    print(str(nfound)+" call matches were made")
    return calls

def convert(ASTs,project_path):
    copy_ASTs = copy.deepcopy(ASTs)
    print("Making first pass..")
    fdefs,imp_obj_strs,imp_mods = firstPass(ASTs)
    #pr.printFnDefs(fdefs)
    imp_funcs,imp_class_strs=matchImpObjStrs(fdefs,imp_obj_strs)
    #pr.printImpClassStrs(imp_class_strs)
    #pr.printImpFuncs(imp_funcs)
    print("Making second pass..")
    calls = secondPass(copy_ASTs,fdefs,imp_funcs,imp_mods,imp_class_strs)
    print(str(len(calls))+" total calls")








