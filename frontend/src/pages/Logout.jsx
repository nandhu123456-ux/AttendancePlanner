function Logout() {


    function logout() {


        localStorage.removeItem(
            "token"
        );


        localStorage.removeItem(
            "student_id"
        );


        window.location = "/login";


    }



    return (

        <button onClick={logout}>

            Logout

        </button>

    )


}


export default Logout;