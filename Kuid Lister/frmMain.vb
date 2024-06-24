Imports System.IO
Imports System.Text.RegularExpressions

Public Class frmMain

    Private Sub Button1_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button1.Click
        Dim lista As String = Nothing  'pentru a memora lista de kuiduri
        Static start_time As DateTime
        Static stop_time As DateTime
        Dim elapsed_time As TimeSpan   'pentru a masura durata procesarii
        Dim nrk, nrfk As Integer  'numarul de kuiduri
        Dim author, kid As Integer 'detaliile kuidului pentru generarea versiunilor
        start_time = Now    'incepe masurarea timpului

        TextBox2.Clear()    'sterge textbox final

        ProgressBar1.Value = 0  'reseteaza progresul

        'gaseste toate match-urile de tip kuid
        Dim matches As MatchCollection = Regex.Matches(TextBox1.Text, "(kuid|KUID)[2]?:[-]?[0-9]*:[-]?[0-9]*(:[0-9]*)?")

        'maximul progresului este cate kuiduri a gasit
        ProgressBar1.Maximum = 3 * matches.Count    'sunt 3 etape de procesare
        nrk = matches.Count 'memoreaza numarul total de kuiduri gasite

        Dim str(nrk) As String 'tabloul de kuiduri gasite
        Dim i, j As Integer
        'Parcurge gasirile
        i = 0
        For Each m As Match In matches
            'Parcurge valorile lor
            For Each c As Capture In m.Captures
                ProgressBar1.Value = ProgressBar1.Value + 1 'progres
                Application.DoEvents()  'pentru a nu da Not Responding
                str(i) = c.Value    'memoreaza kuidul in tablou
                i = i + 1
            Next
        Next

        For i = 0 To nrk - 1    'gaseste kuidurile duplicate si inlocuieste-le cu ""
            ProgressBar1.Value = ProgressBar1.Value + 1 'progres
            Application.DoEvents()  'pentru a nu da Not Responding
            For j = i + 1 To nrk
                If str(i) = str(j) Then
                    str(j) = ""
                End If
            Next
        Next

        nrfk = 0    'numarul de kuiduri unice

        For i = 0 To nrk - 1
            ProgressBar1.Value = ProgressBar1.Value + 1 'progres
            Application.DoEvents()  'pentru a nu da Not Responding
            If str(i) <> "" Then
                If CheckBox1.Checked = False Then
                    nrfk = nrfk + 1 'numara kuidurile unice
                    lista = lista & "<" & str(i) & ">,"    'adauga-le la lista
                Else
                    'generare versiuni kuid
                    author = str(i).Split(":")(1)   'a doua parte din kuid e autourl
                    kid = str(i).Split(":")(2)  'a treia parte din kuid e content id
                    If author < 0 Then 'kuidurile negative nu pot avea versiune
                        nrfk = nrfk + 1 'numara kuidurile unice
                        lista = lista & "<kuid:" & author & ":" & kid & ">,"
                    Else
                        For j = 0 To CInt(TextBox3.Text)
                            Application.DoEvents()  'pentru a nu da Not Responding
                            nrfk = nrfk + 1 'numara kuidurile unice
                            lista = lista & "<kuid2:" & author & ":" & kid & ":" & j & ">,"
                        Next
                    End If
                End If
            End If
        Next

        TextBox2.Text = lista   'afiseaza lista in textbox final
        'sterge ultima virgula
        If TextBox2.Text <> "" Then TextBox2.Text = Strings.Left(TextBox2.Text, Len(TextBox2.Text) - 1)

        'afiseaza numarul de kuiduri gasite si timpul
        stop_time = Now 'opreste masurarea timpului
        elapsed_time = stop_time.Subtract(start_time)   'calculeaza timpul scurs
        'formateaza-l cu 4 zecimale si afiseaza-l in secunde
        Label2.Text = "Listed " & nrfk & " KUIDs in " & elapsed_time.TotalMilliseconds.ToString("0 ms.")

        TextBox2.SelectAll()
        TextBox2.Copy()

    End Sub

    Private Sub Button5_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button5.Click
        TextBox1.Text = TextBox1.Text + My.Computer.Clipboard.GetText()
    End Sub

    Private Sub TextBox3_TextChanged(sender As Object, e As EventArgs) Handles TextBox3.TextChanged
        If Val(TextBox3.Text) > 127 Or Val(TextBox3.Text) < 0 Then
            MessageBox.Show("Versions above 127 or below 0 are invalid!")
        End If
    End Sub

    Private Sub LinkLabel1_LinkClicked(sender As Object, e As LinkLabelLinkClickedEventArgs) Handles LinkLabel1.LinkClicked
        Process.Start("http://vvmm.freeforums.org/")
    End Sub

    Private Sub Form1_Load(sender As Object, e As EventArgs) Handles MyBase.Load

    End Sub

    Private Sub Button2_Click(sender As Object, e As EventArgs) Handles Button2.Click
        TextBox1.Text = ""
    End Sub
End Class
