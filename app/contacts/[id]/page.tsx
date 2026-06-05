import ContactProfile from "@/components/ContactProfile";

export default function ContactPage({ params }: { params: { id: string } }) {
  return <ContactProfile contactId={params.id} />;
}
