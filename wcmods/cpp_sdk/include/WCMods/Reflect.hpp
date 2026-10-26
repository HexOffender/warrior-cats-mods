// WCMods/Reflect.hpp: the game's objects by reflection, checked: a property's value by its path, as the kind
// it is (a bool, a number, text, an object, an enum's name), writing one, the elements of arrays and the pairs
// of maps, a struct's fields, what an object has, and spawning an actor. Game thread only. WCMods.hpp
// includes it; docs/SDK.md, "C++ mods", documents every call.
//
//   auto clan = wcmods::get(cat, L"MeshCustomizationComponent.CustomData.ClanType");   // an enum: clan.text
//   auto tags = wcmods::get(cat, L"Tags");                                              // an array: tags.length
//   wcmods::set(cat, L"CustomTimeDilation", 0.5);
//   for (auto& [tag, count] : wcmods::map_entries(cat, L"rewards")) ...
#pragma once

#include <cmath>
#include <cstdint>
#include <functional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <Unreal/AActor.hpp>
#include <Unreal/Core/Containers/Map.hpp>
#include <Unreal/Core/Containers/ScriptArray.hpp>
#include <Unreal/CoreUObject/UObject/Class.hpp>
#include <Unreal/CoreUObject/UObject/FStrProperty.hpp>
#include <Unreal/CoreUObject/UObject/UnrealType.hpp>
#include <Unreal/FString.hpp>
#include <Unreal/FText.hpp>
#include <Unreal/NameTypes.hpp>
#include <Unreal/Property/FEnumProperty.hpp>
#include <Unreal/Property/FTextProperty.hpp>
#include <Unreal/UObject.hpp>
#include <Unreal/World.hpp>

#include <WCMods/Core.hpp>
#include <WCMods/Game.hpp>

namespace wcmods
{
    using RC::Unreal::FProperty;
    using RC::Unreal::UStruct;

    // What a property holds, as the plain kind it is. `kind` says which of the fields means something:
    // Bool: `b`; Int and Enum: `i` (an enum's name in `text` too); Float: `f`; Text (an FString, FName or
    // FText): `text`; Object: `object` (nullptr when it's unset); Struct, Array and Map: the place, for
    // get/set/elements/map_entries to go on from. None: there's no such property. `type` names the
    // property's class ("FloatProperty", and an enum's or struct's name).
    struct Value
    {
        enum class Kind { None, Bool, Int, Float, Text, Object, Enum, Struct, Array, Map, Other };
        Kind kind{Kind::None};
        bool b{};
        int64_t i{};
        double f{};
        std::wstring text;
        UObject* object{};
        std::wstring type;
        void* at{};            // where the value sits (Struct, Array, Map, and the rest)
        FProperty* property{}; // what describes it
        RC::Unreal::UStruct* layout{};   // a struct's type when no property says: one in the game's own arrays (struct_at)

        explicit operator bool() const { return kind != Kind::None; }
        auto boolean(bool fallback = false) const -> bool { return kind == Kind::Bool ? b : fallback; }
        // Int, Float and Enum as a number; else the fallback.
        auto number(double fallback = 0) const -> double
        {
            return kind == Kind::Float ? f : (kind == Kind::Int || kind == Kind::Enum) ? static_cast<double>(i) : fallback;
        }
        auto string(std::wstring fallback = {}) const -> std::wstring
        {
            return kind == Kind::Text || kind == Kind::Enum ? text : fallback;
        }
        // The value as text, for showing: "true", "1.5", "Otterpaw", an object's name, "{FVector}", "[3]".
        auto shown() const -> std::wstring;

        static auto of(bool v) -> Value { Value r; r.kind = Kind::Bool; r.b = v; return r; }
        static auto of(double v) -> Value
        {
            Value r;
            r.kind = Kind::Float;
            r.f = v;
            r.i = std::isfinite(v) && v > -9.2e18 && v < 9.2e18 ? static_cast<int64_t>(v) : 0;   // the cast is undefined outside
            return r;
        }
        static auto of(int v) -> Value { Value r; r.kind = Kind::Int; r.i = v; r.f = v; return r; }
        static auto of(int64_t v) -> Value { Value r; r.kind = Kind::Int; r.i = v; r.f = static_cast<double>(v); return r; }
        static auto of(std::wstring_view v) -> Value { Value r; r.kind = Kind::Text; r.text = v; return r; }
        static auto of(const wchar_t* v) -> Value { return of(std::wstring_view(v)); }
        static auto of(UObject* v) -> Value { Value r; r.kind = Kind::Object; r.object = v; return r; }
    };

    // One of an object's or struct's properties, from describe().
    struct Member
    {
        std::wstring name;
        std::wstring type;
        Value value;
    };

    namespace detail
    {
        using namespace RC::Unreal;

        inline auto property_type(FProperty* p) -> std::wstring { return p ? p->GetClass().GetFName().ToString() : std::wstring{}; }

        // A struct's properties, deprecated ones too, as UE4SS's field iterator walks them: own_properties()
        // the struct's own (a function's parameters, in order), properties_in_chain() its own and then each
        // parent's. What UStruct::ForEachProperty and ForEachPropertyInChain gave before UE4SS deprecated
        // them; a range-for over either, and returning out of it stops the walk there.
        inline auto own_properties(UStruct* type) -> TFieldRange<FProperty>
        {
            return TFieldRange<FProperty>(type, EFieldIterationFlags::IncludeDeprecated);
        }
        inline auto properties_in_chain(UStruct* type) -> TFieldRange<FProperty>
        {
            return TFieldRange<FProperty>(type, EFieldIterationFlags::Default);
        }

        // "EClanType::RiverClan" -> "RiverClan"
        inline auto short_enum_name(std::wstring name) -> std::wstring
        {
            auto at = name.rfind(L"::");
            return at == std::wstring::npos ? name : name.substr(at + 2);
        }

        inline auto enum_of(FProperty* p, const std::wstring& type) -> UEnum*
        {
            if (type == L"EnumProperty") return static_cast<FEnumProperty*>(p)->GetEnum();
            if (type == L"ByteProperty") return static_cast<FByteProperty*>(p)->GetEnum();
            return nullptr;
        }

        // The value a property holds at `at` (the value's own address, not the container's).
        inline auto read(FProperty* p, void* at) -> Value
        {
            Value v;
            if (!p || !at) return v;
            v.at = at;
            v.property = p;
            v.type = property_type(p);
            const std::wstring& t = v.type;
            if (t == L"BoolProperty")
            {
                v.kind = Value::Kind::Bool;
                v.b = static_cast<FBoolProperty*>(p)->GetPropertyValue(at);
            }
            else if (t == L"FloatProperty" || t == L"DoubleProperty")
            {
                v.kind = Value::Kind::Float;
                v.f = static_cast<FNumericProperty*>(p)->GetFloatingPointPropertyValue(at);
                v.i = static_cast<int64_t>(v.f);
            }
            else if (t == L"EnumProperty" || (t == L"ByteProperty" && static_cast<FByteProperty*>(p)->GetEnum()))
            {
                v.kind = Value::Kind::Enum;
                FNumericProperty* numeric = t == L"EnumProperty" ? static_cast<FEnumProperty*>(p)->GetUnderlyingProp()
                                                                 : static_cast<FNumericProperty*>(p);
                v.i = numeric->GetSignedIntPropertyValue(at);
                v.f = static_cast<double>(v.i);
                if (UEnum* e = enum_of(p, t))
                {
                    v.type = e->GetName();
                    v.text = short_enum_name(e->GetNameByValue(v.i).ToString());
                }
            }
            else if (t == L"ByteProperty" || t == L"Int8Property" || t == L"Int16Property" || t == L"IntProperty" || t == L"Int64Property"
                     || t == L"UInt16Property" || t == L"UInt32Property" || t == L"UInt64Property")
            {
                v.kind = Value::Kind::Int;
                v.i = static_cast<FNumericProperty*>(p)->GetSignedIntPropertyValue(at);
                v.f = static_cast<double>(v.i);
            }
            else if (t == L"StrProperty")
            {
                v.kind = Value::Kind::Text;
                v.text = std::wstring(static_cast<FString*>(at)->operator*());
            }
            else if (t == L"NameProperty")
            {
                v.kind = Value::Kind::Text;
                v.text = static_cast<FName*>(at)->ToString();
            }
            else if (t == L"TextProperty")
            {
                v.kind = Value::Kind::Text;
                v.text = static_cast<FText*>(at)->ToString();
            }
            else if (t == L"ObjectProperty" || t == L"ObjectPtrProperty" || t == L"ClassProperty" || t == L"ClassPtrProperty")
            {
                v.kind = Value::Kind::Object;
                v.object = *static_cast<UObject**>(at);
            }
            else if (t == L"StructProperty")
            {
                v.kind = Value::Kind::Struct;
                if (UScriptStruct* s = static_cast<FStructProperty*>(p)->GetStruct()) v.type = s->GetName();
            }
            else if (t == L"ArrayProperty")
            {
                v.kind = Value::Kind::Array;
            }
            else if (t == L"MapProperty")
            {
                v.kind = Value::Kind::Map;
            }
            else
            {
                v.kind = Value::Kind::Other;
            }
            return v;
        }

        // A property of a struct's, by name, through its parents.
        inline auto struct_property(UStruct* type, std::wstring_view name) -> FProperty*
        {
            if (!type) return nullptr;
            for (FProperty* p : properties_in_chain(type))
                if (p->GetName() == name) return p;
            return nullptr;
        }

        // Where a path's steps lead: `container` is an object or a struct's bytes, `type` what describes it.
        struct Place
        {
            void* container{};
            UStruct* type{};
            bool object{};   // the container is a UObject (its own class describes it)
        };

        inline auto step(const Place& place, std::wstring_view name) -> Value
        {
            if (!place.container) return {};
            FProperty* p = place.object ? static_cast<UObject*>(place.container)->GetPropertyByNameInChain(std::wstring(name).c_str())
                                        : struct_property(place.type, name);
            if (!p) return {};
            return read(p, p->ContainerPtrToValuePtr<void>(place.container));
        }

        inline auto element(const Value& array, int index) -> Value
        {
            if (array.kind != Value::Kind::Array || !array.property || !array.at) return {};
            auto* ap = static_cast<FArrayProperty*>(array.property);
            FScriptArrayHelper helper(ap, array.at);
            if (!helper.IsValidIndex(index)) return {};
            return read(ap->GetInner(), helper.GetRawPtr(index));
        }

        inline auto place_of(const Value& v) -> Place
        {
            if (v.kind == Value::Kind::Object) return {v.object, v.object ? v.object->GetClassPrivate() : nullptr, true};
            if (v.kind == Value::Kind::Struct)
                return {v.at, v.property ? static_cast<UStruct*>(static_cast<FStructProperty*>(v.property)->GetStruct()) : v.layout, false};
            return {};
        }

        // Walk "A.B[2].C" from an object, a struct or an array (a Value a get gave).
        inline auto walk(Value here, std::wstring_view path) -> Value
        {
            if (!here) return {};
            size_t pos = 0;
            while (pos < path.size())
            {
                size_t end = path.find_first_of(L".[", pos);
                std::wstring_view name = path.substr(pos, end == std::wstring_view::npos ? std::wstring_view::npos : end - pos);
                if (!name.empty())
                {
                    here = step(place_of(here), name);
                    if (!here) return {};
                }
                if (end == std::wstring_view::npos) break;
                pos = end;
                while (pos < path.size() && path[pos] == L'[')
                {
                    size_t close = path.find(L']', pos);
                    if (close == std::wstring_view::npos) return {};
                    int index = 0;
                    for (size_t k = pos + 1; k < close; ++k)
                    {
                        if (path[k] < L'0' || path[k] > L'9') return {};
                        index = index * 10 + (path[k] - L'0');
                    }
                    here = element(here, index);
                    if (!here) return {};
                    pos = close + 1;
                }
                if (pos < path.size() && path[pos] == L'.') ++pos;
            }
            return here;
        }

        inline auto write(const Value& target, const Value& value) -> bool
        {
            if (!target || !target.property || !target.at) return false;
            FProperty* p = target.property;
            const std::wstring t = property_type(p);
            switch (target.kind)
            {
            case Value::Kind::Bool:
                if (value.kind != Value::Kind::Bool) return false;
                static_cast<FBoolProperty*>(p)->SetPropertyValue(target.at, value.b);
                return true;
            case Value::Kind::Float:
                if (value.kind != Value::Kind::Float && value.kind != Value::Kind::Int) return false;
                static_cast<FNumericProperty*>(p)->SetFloatingPointPropertyValue(target.at, value.number());
                return true;
            case Value::Kind::Int:
                if (value.kind != Value::Kind::Int && value.kind != Value::Kind::Float) return false;
                static_cast<FNumericProperty*>(p)->SetIntPropertyValue(target.at, static_cast<int64>(value.number()));
                return true;
            case Value::Kind::Enum:
            {
                FNumericProperty* numeric = t == L"EnumProperty" ? static_cast<FEnumProperty*>(p)->GetUnderlyingProp()
                                                                 : static_cast<FNumericProperty*>(p);
                if (value.kind == Value::Kind::Int || value.kind == Value::Kind::Enum || value.kind == Value::Kind::Float)
                {
                    numeric->SetIntPropertyValue(target.at, static_cast<int64>(value.number()));
                    return true;
                }
                if (value.kind == Value::Kind::Text)
                {
                    UEnum* e = enum_of(p, t);
                    if (!e) return false;
                    for (auto& pair : e->ForEachName())
                    {
                        if (short_enum_name(pair.Key.ToString()) == value.text || pair.Key.ToString() == value.text)
                        {
                            numeric->SetIntPropertyValue(target.at, pair.Value);
                            return true;
                        }
                    }
                }
                return false;
            }
            case Value::Kind::Text:
                if (value.kind != Value::Kind::Text) return false;
                if (t == L"StrProperty") *static_cast<FString*>(target.at) = FString(value.text.c_str());
                else if (t == L"NameProperty") *static_cast<FName*>(target.at) = FName(value.text.c_str());
                else return false;   // FText is made by the game; set the FString it shows instead
                return true;
            case Value::Kind::Object:
                if (value.kind != Value::Kind::Object) return false;
                *static_cast<UObject**>(target.at) = value.object;
                return true;
            default:
                return false;
            }
        }
    } // namespace detail

    inline auto Value::shown() const -> std::wstring
    {
        switch (kind)
        {
        case Kind::None: return L"(none)";
        case Kind::Bool: return b ? L"true" : L"false";
        case Kind::Int: return std::to_wstring(i);
        case Kind::Float: return std::format(L"{}", f);
        case Kind::Text: return text;
        case Kind::Enum: return text.empty() ? std::to_wstring(i) : text;
        case Kind::Object: return object ? object->GetName() : L"(null)";
        case Kind::Struct: return L"{" + type + L"}";
        case Kind::Array:
        {
            if (!property || !at) return L"[]";
            RC::Unreal::FScriptArrayHelper helper(static_cast<RC::Unreal::FArrayProperty*>(property), at);
            return L"[" + std::to_wstring(helper.Num()) + L"]";
        }
        case Kind::Map: return L"{map}";
        default: return L"(" + type + L")";
        }
    }

    // A property's value by its path from an object: names joined with dots, an element with [i]:
    //   wcmods::get(cat, L"Controller.PlayerState")          an object
    //   wcmods::get(cat, L"CustomTimeDilation").number()     a float
    //   wcmods::get(cat, L"Tags[0]").string()                an array's element
    //   wcmods::get(cat, L"MeshCustomizationComponent.CustomData.ClanType").text   an enum's name
    // A Value whose kind is None when there's no such property, or an object on the way is unset.
    inline auto get(UObject* object, std::wstring_view path) -> Value
    {
        return object ? detail::walk(Value::of(object), path) : Value{};
    }

    // The same from a Value that is a struct, an object or an array (one get's result, then further:
    // get(custom, L"ClanType"), get(tags, L"[0]")).
    inline auto get(const Value& from, std::wstring_view path) -> Value { return detail::walk(from, path); }

    // Write a property: a bool, a number (to an int, float or enum), text (to an FString or FName, or an
    // enum's name), or an object. False when there's no such property, or it isn't that kind.
    inline auto set(UObject* object, std::wstring_view path, const Value& value) -> bool { return detail::write(get(object, path), value); }
    inline auto set(UObject* object, std::wstring_view path, bool value) -> bool { return set(object, path, Value::of(value)); }
    inline auto set(UObject* object, std::wstring_view path, double value) -> bool { return set(object, path, Value::of(value)); }
    inline auto set(UObject* object, std::wstring_view path, int value) -> bool { return set(object, path, Value::of(value)); }
    inline auto set(UObject* object, std::wstring_view path, std::wstring_view value) -> bool { return set(object, path, Value::of(value)); }
    inline auto set(UObject* object, std::wstring_view path, const wchar_t* value) -> bool { return set(object, path, Value::of(value)); }
    inline auto set(UObject* object, std::wstring_view path, UObject* value) -> bool { return set(object, path, Value::of(value)); }

    // An array's elements (a Value of kind Array), each as a Value.
    inline auto elements(const Value& array) -> std::vector<Value>
    {
        std::vector<Value> out;
        if (array.kind != Value::Kind::Array || !array.property || !array.at) return out;
        RC::Unreal::FScriptArrayHelper helper(static_cast<RC::Unreal::FArrayProperty*>(array.property), array.at);
        for (int i = 0; i < helper.Num(); ++i) out.push_back(detail::element(array, i));
        return out;
    }
    inline auto elements(UObject* object, std::wstring_view path) -> std::vector<Value> { return elements(get(object, path)); }

    // A map's pairs (a Value of kind Map), each key and value as a Value: the game's tag-count maps give
    // the tag's name and the count.
    inline auto map_entries(const Value& map) -> std::vector<std::pair<Value, Value>>
    {
        std::vector<std::pair<Value, Value>> out;
        if (map.kind != Value::Kind::Map || !map.property || !map.at) return out;
        auto* mp = static_cast<RC::Unreal::FMapProperty*>(map.property);
        auto* m = static_cast<RC::Unreal::FScriptMap*>(map.at);
        const auto& layout = mp->GetMapLayout();
        for (int i = 0; i < m->GetMaxIndex(); ++i)
        {
            if (!m->IsValidIndex(i)) continue;
            auto* pair = static_cast<uint8_t*>(m->GetData(i, layout));
            out.emplace_back(detail::read(mp->GetKeyProp(), pair), detail::read(mp->GetValueProp(), pair + layout.ValueOffset));
        }
        return out;
    }
    inline auto map_entries(UObject* object, std::wstring_view path) -> std::vector<std::pair<Value, Value>>
    {
        return map_entries(get(object, path));
    }

    // Every property of an object (its class and the parents'), or of a struct Value, with its value now.
    inline auto describe(UObject* object) -> std::vector<Member>
    {
        std::vector<Member> out;
        if (!object || !object->GetClassPrivate()) return out;
        for (FProperty* p : detail::properties_in_chain(object->GetClassPrivate()))
        {
            Value v = detail::read(p, p->ContainerPtrToValuePtr<void>(object));
            out.push_back({p->GetName(), v.type, v});
        }
        return out;
    }
    inline auto describe(const Value& value) -> std::vector<Member>
    {
        std::vector<Member> out;
        if (value.kind == Value::Kind::Object) return describe(value.object);
        if (value.kind != Value::Kind::Struct) return out;
        detail::Place place = detail::place_of(value);
        if (!place.type) return out;
        for (FProperty* p : detail::properties_in_chain(place.type))
        {
            Value v = detail::read(p, p->ContainerPtrToValuePtr<void>(place.container));
            out.push_back({p->GetName(), v.type, v});
        }
        return out;
    }

    // A struct Value over bytes you point at, by the struct's type or its path
    // ("/Script/SwtAdventure.SwtAdventureAttackMoveStruct"): for a struct in one of the game's own arrays, which
    // no property describes (Fighter::moves()). get(), describe() and set() work on it as on any struct Value;
    // the bytes stay the game's, so use it while they last. None without the type or the bytes.
    inline auto struct_at(RC::Unreal::UStruct* type, void* at) -> Value
    {
        if (!type || !at) return {};
        Value v;
        v.kind = Value::Kind::Struct;
        v.at = at;
        v.layout = type;
        v.type = type->GetName();
        return v;
    }
    inline auto struct_at(const TCHAR* struct_path, void* at) -> Value
    {
        UObject* o = object(struct_path);
        if (!o || !o->IsA(RC::Unreal::UStruct::StaticClass())) return {};   // a path to something that isn't a struct
        return struct_at(static_cast<RC::Unreal::UStruct*>(o), at);
    }

    // Write into a struct or object a get() gave: set(custom, L"ClanType", L"RiverClan").
    inline auto set(const Value& from, std::wstring_view path, const Value& value) -> bool { return detail::write(get(from, path), value); }
    inline auto set(const Value& from, std::wstring_view path, bool value) -> bool { return set(from, path, Value::of(value)); }
    inline auto set(const Value& from, std::wstring_view path, double value) -> bool { return set(from, path, Value::of(value)); }
    inline auto set(const Value& from, std::wstring_view path, int value) -> bool { return set(from, path, Value::of(value)); }
    inline auto set(const Value& from, std::wstring_view path, std::wstring_view value) -> bool { return set(from, path, Value::of(value)); }
    inline auto set(const Value& from, std::wstring_view path, const wchar_t* value) -> bool { return set(from, path, Value::of(value)); }
    inline auto set(const Value& from, std::wstring_view path, UObject* value) -> bool { return set(from, path, Value::of(value)); }

    // ============================================================================================ calling by reflection
    // A reflected function's parameters, laid out as it wants them (the game's own property descriptions
    // say where each is): set the inputs by name, call, then read the outputs and the return value. For a
    // function `call` with a struct is awkward for: outputs that are structs (a hit result), inputs that
    // are arrays or strings, returns that are enums (read with their names) or texts.
    class Params
    {
      public:
        explicit Params(UFunction* function) : m_function(function), m_bytes(function ? function->GetParmsSize() : 0, 0) {}
        // What the engine put in the buffer (a string or array it gave back) is its to free: each parameter
        // is destroyed as its property says. One Params owns its bytes; moving passes them on.
        ~Params()
        {
            if (!m_function || m_bytes.empty()) return;
            for (FProperty* p : detail::own_properties(m_function)) p->DestroyValue_InContainer(m_bytes.data());
        }
        Params(Params&& other) noexcept : m_function(other.m_function), m_bytes(std::move(other.m_bytes)) { other.m_function = nullptr; }
        auto operator=(Params&& other) noexcept -> Params&
        {
            if (this != &other)
            {
                this->~Params();
                m_function = other.m_function;
                m_bytes = std::move(other.m_bytes);
                other.m_function = nullptr;
            }
            return *this;
        }
        Params(const Params&) = delete;
        auto operator=(const Params&) -> Params& = delete;

        auto function() const -> UFunction* { return m_function; }
        auto bytes() -> void* { return m_bytes.data(); }
        // A parameter's value, as get() gives it (`L"ReturnValue"` for what the function gave back).
        auto get(std::wstring_view name) -> Value
        {
            FProperty* p = find(name);
            return p ? detail::read(p, p->ContainerPtrToValuePtr<void>(m_bytes.data())) : Value{};
        }
        // Set a parameter: a bool, number, text (an FString, FName or enum's name) or object.
        auto set(std::wstring_view name, const Value& value) -> bool { return detail::write(get(name), value); }
        auto set(std::wstring_view name, bool value) -> bool { return set(name, Value::of(value)); }
        auto set(std::wstring_view name, double value) -> bool { return set(name, Value::of(value)); }
        auto set(std::wstring_view name, int value) -> bool { return set(name, Value::of(value)); }
        auto set(std::wstring_view name, std::wstring_view value) -> bool { return set(name, Value::of(value)); }
        auto set(std::wstring_view name, const wchar_t* value) -> bool { return set(name, Value::of(value)); }
        auto set(std::wstring_view name, UObject* value) -> bool { return set(name, Value::of(value)); }
        // Where a parameter's bytes are, for a struct (an FVector in: `*static_cast<FVector*>(p.raw(L"Start")) = ...`).
        auto raw(std::wstring_view name) -> void*
        {
            FProperty* p = find(name);
            return p ? p->ContainerPtrToValuePtr<void>(m_bytes.data()) : nullptr;
        }
        auto has(std::wstring_view name) -> bool { return find(name) != nullptr; }
        // The parameters by position (the return value last), for functions whose names you'd rather not
        // depend on: nth(0) is the first.
        auto nth(int index) -> Value
        {
            FProperty* p = find(index);
            return p ? detail::read(p, p->ContainerPtrToValuePtr<void>(m_bytes.data())) : Value{};
        }
        auto set_nth(int index, const Value& value) -> bool { return detail::write(nth(index), value); }
        auto count() -> int
        {
            int n = 0;
            if (m_function)
                for ([[maybe_unused]] FProperty* p : detail::own_properties(m_function)) ++n;
            return n;
        }

      private:
        UFunction* m_function;
        std::vector<uint8_t> m_bytes;

        auto find(int index) -> FProperty*
        {
            if (!m_function || index < 0) return nullptr;
            for (FProperty* p : detail::own_properties(m_function))
                if (index-- == 0) return p;
            return nullptr;
        }

        auto find(std::wstring_view name) -> FProperty*
        {
            if (!m_function) return nullptr;
            for (FProperty* p : detail::own_properties(m_function))
                if (p->GetName() == name) return p;
            return nullptr;
        }
    };

    // Call one of an object's reflected functions through its parameters by name: `fill(params)` sets the
    // inputs, and what comes back holds the outputs and `ReturnValue`. nullopt when the object or the
    // function isn't there:
    //   auto r = wcmods::call_reflected(manager, STR("GetQuestStatus"), [&](wcmods::Params& p) {
    //       wcmods::set(p.get(L"QuestTag"), L"TagName", tag);
    //   });
    //   if (r) status = r->get(L"ReturnValue").text;   // an enum, by name
    inline auto call_reflected(UObject* object, const TCHAR* function, const std::function<void(Params&)>& fill = {})
            -> std::optional<Params>
    {
        if (!object) return std::nullopt;
        UFunction* fn = object->GetFunctionByNameInChain(function);
        if (!fn) return std::nullopt;
        Params params(fn);
        if (fill) fill(params);
        object->ProcessEvent(fn, params.bytes());
        return params;
    }

    // Spawn an actor of a class (by its path) at a place; nullptr when the class isn't there or the world
    // isn't up. The game's own cats need more than this (see the Lua module's Game.npcs); it's for plain actors.
    inline auto spawn(const TCHAR* class_path, Vec3 at) -> UObject*
    {
        UClass* cls = find_class(class_path);
        auto* w = static_cast<RC::Unreal::UWorld*>(world());
        if (!cls || !w) return nullptr;
        FVector where = to_fvector(at);
        return w->SpawnActor(cls, &where, nullptr);
    }

    // Take an actor out of the world. False when it isn't there.
    inline auto destroy(UObject* actor) -> bool
    {
        if (!actor) return false;
        static_cast<AActor*>(actor)->K2_DestroyActor();
        return true;
    }
} // namespace wcmods
